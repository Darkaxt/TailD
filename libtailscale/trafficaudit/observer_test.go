// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package trafficaudit

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"net/netip"
	"sync"
	"testing"

	"github.com/tailscale/wireguard-go/tun"
	"golang.org/x/net/dns/dnsmessage"
)

func udp(body []byte, reply bool) []byte {
	p := make([]byte, 28+len(body))
	p[0] = 0x45
	binary.BigEndian.PutUint16(p[2:], uint16(len(p)))
	p[9] = 17
	copy(p[12:], []byte{100, 64, 0, 1})
	copy(p[16:], []byte{100, 100, 100, 100})
	binary.BigEndian.PutUint16(p[20:], 12345)
	binary.BigEndian.PutUint16(p[22:], 53)
	binary.BigEndian.PutUint16(p[24:], uint16(8+len(body)))
	copy(p[28:], body)
	if reply {
		copy(p[12:], []byte{100, 100, 100, 100})
		copy(p[16:], []byte{100, 64, 0, 1})
		binary.BigEndian.PutUint16(p[20:], 53)
		binary.BigEndian.PutUint16(p[22:], 12345)
	}
	return p
}

func dnsFact(t *testing.T, name string, reply bool, at int64, ttl uint32) Fact {
	t.Helper()
	n := dnsmessage.MustNewName(name)
	m := dnsmessage.Message{Header: dnsmessage.Header{ID: 7, Response: reply}, Questions: []dnsmessage.Question{{Name: n, Type: dnsmessage.TypeA, Class: dnsmessage.ClassINET}}}
	if reply {
		m.Answers = []dnsmessage.Resource{{Header: dnsmessage.ResourceHeader{Name: n, Type: dnsmessage.TypeA, Class: dnsmessage.ClassINET, TTL: ttl}, Body: &dnsmessage.AResource{A: [4]byte{100, 64, 0, 2}}}}
	}
	b, err := m.Pack()
	if err != nil {
		t.Fatal(err)
	}
	f := parsePacket(udp(b, reply), !reply)
	f.At = at
	f.UID = 10001
	f.Scope.ID = "scope"
	return f
}

func TestCandidatesRequirePrecedingMatchedScopeAndTTL(t *testing.T) {
	s := dnsState{queries: map[string]query{}, answers: map[string]map[string]Candidate{}}
	for _, name := range []string{"Alpha.test.", "beta.test.", "Alpha.test."} {
		q := dnsFact(t, name, false, 1000, 1)
		s.observe(&q)
		r := dnsFact(t, name, true, 1100, 1)
		s.observe(&r)
		if r.DNS == nil || !r.DNS.Matched || r.DNS.QueryUID != 10001 {
			t.Fatalf("query evidence: %+v", r.DNS)
		}
	}
	f := Fact{At: 1200, Remote: "100.64.0.2", Scope: Scope{ID: "scope"}}
	s.observe(&f)
	if len(f.Candidates) != 2 || f.Candidates[0].Name != "alpha.test" {
		t.Fatalf("distinct stable candidates: %+v", f.Candidates)
	}
	f.Candidates = nil
	f.NetworkGeneration = 1
	s.observe(&f)
	if len(f.Candidates) != 0 {
		t.Fatal("cross-network candidate")
	}
	f.NetworkGeneration = 0
	f.Candidates = nil
	f.Scope.ID = "other"
	s.observe(&f)
	if len(f.Candidates) != 0 {
		t.Fatal("cross-scope candidate")
	}
	f.Scope.ID = "scope"
	f.At = 2100
	s.observe(&f)
	if len(f.Candidates) != 0 {
		t.Fatal("expired answer")
	}
}

func TestNegativeDNSIsNotProofOfBlock(t *testing.T) {
	s := dnsState{queries: map[string]query{}, answers: map[string]map[string]Candidate{}}
	q := dnsFact(t, "blocked.test.", false, 1000, 0)
	s.observe(&q)
	r := dnsFact(t, "blocked.test.", true, 1100, 0)
	var m dnsmessage.Message
	if err := m.Unpack(r.dns); err != nil {
		t.Fatal(err)
	}
	m.RCode = dnsmessage.RCodeNameError
	m.Answers = nil
	r.dns, _ = m.Pack()
	s.observe(&r)
	if r.DNS == nil || r.DNS.Blocked || !r.DNS.Matched {
		t.Fatalf("negative response misclassified: %+v", r.DNS)
	}
	q = dnsFact(t, "explicit.test.", false, 2000, 0)
	s.observe(&q)
	r = dnsFact(t, "explicit.test.", true, 2100, 0)
	_ = m.Unpack(r.dns)
	m.Additionals = []dnsmessage.Resource{{Header: dnsmessage.ResourceHeader{Name: dnsmessage.MustNewName("."), Type: dnsmessage.TypeOPT}, Body: &dnsmessage.OPTResource{Options: []dnsmessage.Option{{Code: 15, Data: []byte{0, 15}}}}}}
	r.dns, _ = m.Pack()
	s.observe(&r)
	if !r.DNS.Blocked || r.DNS.QueryUID != 10001 {
		t.Fatalf("explicit EDE lost: %+v", r.DNS)
	}
}

type fakeDevice struct {
	tun.Device
	count  int
	err    error
	packet []byte
}

func (f *fakeDevice) Write(_ [][]byte, _ int) (int, error) { return f.count, f.err }
func (f *fakeDevice) Read(s []byte, p []tun.ReadPacket) (int, error) {
	copy(s[3:], f.packet)
	p[0] = tun.ReadPacket{Offset: 3, Size: len(f.packet)}
	return 1, f.err
}

func TestDeviceCountsOnlySuccessfulDeliveryAndPreservesErrors(t *testing.T) {
	commits := make(chan Batch, 4)
	o := New(func(int, string, string, uint16, uint16) int32 { return 10001 }, func(v string) bool {
		var b Batch
		if err := json.Unmarshal([]byte(v), &b); err != nil {
			t.Error(err)
		}
		commits <- b
		return true
	})
	o.Configure("test")
	defer o.Configure("")
	problem := errors.New("handoff")
	f := &fakeDevice{err: problem, packet: udp(nil, false)}
	d := Device{Device: f, Observer: o, Scope: Scope{ID: "one"}}
	if n, e := d.Write([][]byte{f.packet}, 0); n != 0 || e != problem {
		t.Fatal("write contract changed")
	}
	p := make([]tun.ReadPacket, 1)
	if n, e := d.Read(make([]byte, 100), p); n != 1 || e != problem {
		t.Fatal("read contract changed")
	}
	b := <-commits
	if len(b.Facts) != 1 || !b.Facts[0].Upload || b.Facts[0].Bytes != len(f.packet) {
		t.Fatalf("bad read accounting %+v", b)
	}
	f.count = len(f.packet)
	f.err = nil
	if n, e := d.Write([][]byte{f.packet}, 0); n != len(f.packet) || e != nil {
		t.Fatal("Android byte-return contract changed")
	}
	b = <-commits
	if len(b.Facts) != 1 || b.Facts[0].Upload || b.Facts[0].Bytes != len(f.packet) || b.Facts[0].Packets != 1 {
		t.Fatal("bad successful write accounting")
	}
	f.count = 12
	f.err = problem
	if n, e := d.Write([][]byte{f.packet}, 0); n != 12 || e != problem {
		t.Fatal("partial byte-return contract changed")
	}
	b = <-commits
	if len(b.Facts) != 1 || b.Facts[0].Bytes != 12 || b.Facts[0].Packets != 0 || b.Facts[0].Unknown == "" {
		t.Fatal("partial write invented a packet destination")
	}

}

func TestCanonicalAndMalformedPackets(t *testing.T) {
	for _, raw := range []string{"a..test", "é.test", "", string(make([]byte, 254))} {
		if CanonicalName(raw) != "" {
			t.Fatal(raw)
		}
	}
	if CanonicalName("XN--EXAMPLE.test.") != "xn--example.test" {
		t.Fatal("ASCII rule changed")
	}
	for n := 0; n < 48; n++ {
		p := make([]byte, n)
		if n > 0 {
			p[0] = 0x60
		}
		f := parsePacket(p, true)
		if f.Unknown == "" {
			t.Fatalf("malformed length %d accepted", n)
		}
	}
}

func TestBoundedQueueAndRecordingEpochs(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	next := make(chan Batch, 1)
	var once sync.Once
	o := New(func(int, string, string, uint16, uint16) int32 {
		once.Do(func() { close(entered) })
		<-release
		return 10001
	}, func(value string) bool {
		var b Batch
		if json.Unmarshal([]byte(value), &b) != nil {
			return false
		}
		if b.Session == "new" {
			next <- b
			return true
		}
		return false // An obsolete epoch is never adopted or replayed by the sink.
	})
	o.Configure("old")
	o.Observe(udp(nil, false), true, Scope{ID: "route-a"})
	<-entered
	for i := 0; i < queueSize+7; i++ {
		o.Observe(udp(nil, false), true, Scope{ID: "route-a"})
	}
	var status Batch
	if err := json.Unmarshal([]byte(o.Configure("")), &status); err != nil {
		t.Fatal(err)
	}
	if status.Session != "old" || status.Dropped != 7 {
		t.Fatalf("bounded acquisition loss: %+v", status)
	}
	close(release)
	o.Configure("new")
	defer o.Configure("")
	o.Observe(udp(nil, false), true, Scope{ID: "route-b"})
	b := <-next
	if b.Session != "new" || b.Sequence != 1 || len(b.Facts) != 1 || b.Facts[0].Scope.ID != "route-b" || len(b.Facts[0].Candidates) != 0 {
		t.Fatalf("recording/route epochs mixed: %+v", b)
	}
}

func TestUnsupportedDNSMetadataKeepsSupportedOwnershipTuple(t *testing.T) {
	packet := udp(make([]byte, 5000), false)
	fact := parsePacket(packet, true)
	if !fact.tuple || fact.Unknown != "DNS metadata size limit" || len(fact.dns) != 0 || fact.Bytes != len(packet) {
		t.Fatalf("DNS limits changed byte/owner evidence: %+v", fact)
	}
}

func TestIPv6OwnershipAndUnassignedFragmentsPreserveBytes(t *testing.T) {
	p := make([]byte, 60)
	p[0] = 0x60
	binary.BigEndian.PutUint16(p[4:], 20)
	p[6] = 6
	local := netip.MustParseAddr("fd7a:115c:a1e0::1").As16()
	remote := netip.MustParseAddr("2001:db8::2").As16()
	copy(p[8:24], local[:])
	copy(p[24:40], remote[:])
	binary.BigEndian.PutUint16(p[40:], 12345)
	binary.BigEndian.PutUint16(p[42:], 443)
	p[52] = 0x50
	upload := parsePacket(p, true)
	if !upload.tuple || upload.Local != "fd7a:115c:a1e0::1" || upload.Remote != "2001:db8::2" || upload.LocalPort != 12345 || upload.RemotePort != 443 || upload.Bytes != len(p) {
		t.Fatalf("IPv6 owner tuple lost: %+v", upload)
	}
	copy(p[8:24], remote[:])
	copy(p[24:40], local[:])
	binary.BigEndian.PutUint16(p[40:], 443)
	binary.BigEndian.PutUint16(p[42:], 12345)
	download := parsePacket(p, false)
	if !download.tuple || download.Local != upload.Local || download.Remote != upload.Remote || download.LocalPort != upload.LocalPort || download.RemotePort != upload.RemotePort || download.Bytes != len(p) {
		t.Fatalf("IPv6 download tuple reversed: %+v", download)
	}
	p[6] = 44
	fragment := parsePacket(p, false)
	if fragment.tuple || fragment.Unknown != "fragmented IPv6 packet" || fragment.Bytes != len(p) || fragment.Packets != 1 {
		t.Fatalf("Fragment invented ownership or lost measured bytes: %+v", fragment)
	}
}

func TestFailedAcknowledgementIsCountedWithoutReplayingBytes(t *testing.T) {
	commits := make(chan Batch)
	o := New(func(int, string, string, uint16, uint16) int32 { return -1 }, func(value string) bool {
		var batch Batch
		if err := json.Unmarshal([]byte(value), &batch); err != nil {
			t.Error(err)
		}
		commits <- batch
		return batch.Sequence != 1
	})
	o.Configure("ack-fixture")
	defer o.Configure("")
	o.Observe(udp(nil, false), true, Scope{ID: "scope"})
	first := <-commits
	o.Observe(udp(nil, false), true, Scope{ID: "scope"})
	second := <-commits
	if first.Sequence != 1 || second.Sequence != 2 || second.Unacknowledged != 1 || len(second.Facts) != 1 || second.Facts[0].Bytes != len(udp(nil, false)) {
		t.Fatalf("Failed acknowledgement was hidden or replayed: first=%+v next=%+v", first, second)
	}
}
