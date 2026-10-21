// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause

// Package trafficaudit observes metadata without owning or changing packet delivery.
package trafficaudit

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/netip"
	"sort"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/net/dns/dnsmessage"
)

const queueSize = 2048

type Scope struct {
	ID            string `json:"id"`
	Configuration string `json:"configuration"`
}

type Candidate struct {
	Name     string `json:"name"`
	AnswerAt int64  `json:"answerAt"`
	Expires  int64  `json:"expires"`
	Resolver string `json:"resolver"`
}

type DNS struct {
	ID             uint16      `json:"id"`
	Type           uint16      `json:"type"`
	Class          uint16      `json:"class"`
	Resolver       string      `json:"resolver"`
	QueryAt        int64       `json:"queryAt"`
	Name           string      `json:"name"`
	Canonical      string      `json:"canonical"`
	Response       bool        `json:"response"`
	Code           int         `json:"code"`
	Blocked        bool        `json:"blocked"`
	QueryUID       int32       `json:"queryUid"`
	Matched        bool        `json:"matched"`
	Answers        []DNSAnswer `json:"answers,omitempty"`
	ExtendedErrors []uint16    `json:"extendedErrors,omitempty"`
}

type DNSAnswer struct {
	Owner   string `json:"owner"`
	Address string `json:"address"`
	TTL     uint32 `json:"ttl"`
}

type Fact struct {
	Observation       string      `json:"observation"`
	NetworkGeneration uint64      `json:"networkGeneration"`
	NetworkName       string      `json:"networkName"`
	At                int64       `json:"at"`
	Scope             Scope       `json:"scope"`
	Upload            bool        `json:"upload"`
	Bytes             int         `json:"bytes"`
	Packets           int         `json:"packets"`
	Protocol          int         `json:"protocol"`
	Local             string      `json:"local"`
	Remote            string      `json:"remote"`
	LocalPort         uint16      `json:"localPort"`
	RemotePort        uint16      `json:"remotePort"`
	UID               int32       `json:"uid"`
	LookupAt          int64       `json:"lookupAt"`
	Unknown           string      `json:"unknown,omitempty"`
	DNS               *DNS        `json:"dns,omitempty"`
	Candidates        []Candidate `json:"candidates,omitempty"`
	CandidateCoverage string      `json:"candidateCoverage"`
	tuple             bool
	dns               []byte
}

type Batch struct {
	Session        string `json:"session"`
	Sequence       uint64 `json:"sequence"`
	Dropped        uint64 `json:"dropped"`
	Unacknowledged uint64 `json:"unacknowledged"`
	Facts          []Fact `json:"facts"`
}

type Owner func(protocol int, local, remote string, localPort, remotePort uint16) int32
type Sink func(string) bool

type recording struct {
	id             string
	queue          chan Fact
	done           chan struct{}
	dropped        atomic.Uint64
	unacknowledged atomic.Uint64
}

// Observer's pointer swap is the acquisition boundary. A disabled observer never copies data.
type Observer struct {
	mu              sync.Mutex
	current         atomic.Pointer[recording]
	owner           Owner
	sink            Sink
	networkSequence atomic.Uint64
	network         atomic.Pointer[network]
}

type network struct {
	generation uint64
	name       string
}

// MarkNetwork follows the existing platform network-change event. It never
// changes routing or enables capture, and invalidates DNS joins across networks.
func (o *Observer) MarkNetwork(name string) {
	n := &network{o.networkSequence.Add(1), name}
	o.network.Store(n)
	if r := o.current.Load(); r != nil {
		f := Fact{Observation: "network-change", At: time.Now().UnixMilli(), UID: -1, Scope: Scope{ID: "network", Configuration: "{}"}, NetworkGeneration: n.generation, NetworkName: n.name, Unknown: "Physical network changed; unobserved transition activity remains unknown"}
		select {
		case r.queue <- f:
		default:
			r.dropped.Add(1)
		}
	}
}

func (o *Observer) stampNetwork(f *Fact) {
	if n := o.network.Load(); n != nil {
		f.NetworkGeneration = n.generation
		f.NetworkName = n.name
	}
}

func (f *Fact) dnsScope() string {
	return fmt.Sprintf("%s/network:%d", f.Scope.ID, f.NetworkGeneration)
}

func New(owner Owner, sink Sink) *Observer { return &Observer{owner: owner, sink: sink} }

// Configure invalidates the prior epoch. The sink independently rejects stale epochs.
func (o *Observer) Configure(id string) string {
	o.mu.Lock()
	defer o.mu.Unlock()
	old := o.current.Swap(nil)
	if old != nil {
		close(old.done)
	}
	var status Batch
	if old != nil {
		status = Batch{Session: old.id, Dropped: old.dropped.Load(), Unacknowledged: old.unacknowledged.Load()}
	}
	if id != "" {
		r := &recording{id: id, queue: make(chan Fact, queueSize), done: make(chan struct{})}
		o.current.Store(r)
		go o.run(r)
	}
	b, _ := json.Marshal(status)
	return string(b)
}

// Observe must be called only for packets actually read or successfully written.
// It performs bounded header work, a bounded DNS copy and a nonblocking queue send.
func (o *Observer) Observe(packet []byte, upload bool, scope Scope) {
	r := o.current.Load()
	if r == nil {
		return
	}
	f := parsePacket(packet, upload)
	f.At = time.Now().UnixMilli()
	f.Scope = scope
	o.stampNetwork(&f)
	select {
	case r.queue <- f:
	default:
		r.dropped.Add(1)
	}
}

func (o *Observer) observeUnassignedWrite(bytes int, scope Scope) {
	r := o.current.Load()
	if r == nil {
		return
	}
	f := Fact{Observation: "partial-write", At: time.Now().UnixMilli(), Scope: scope, Bytes: bytes, UID: -1, Unknown: "Partial TUN write: packet count and destinations unknown"}
	o.stampNetwork(&f)
	select {
	case r.queue <- f:
	default:
		r.dropped.Add(1)
	}
}

func (o *Observer) run(r *recording) {
	state := dnsState{queries: make(map[string]query), answers: make(map[string]map[string]Candidate)}
	var seq uint64
	for {
		var first Fact
		select {
		case <-r.done:
			return
		case first = <-r.queue:
		}
		facts := []Fact{first}
		for len(facts) < 128 {
			select {
			case f := <-r.queue:
				facts = append(facts, f)
			default:
				goto collected
			}
		}
	collected:
		for i := range facts {
			f := &facts[i]
			f.UID = -1
			f.LookupAt = 0
			if f.tuple {
				f.LookupAt = time.Now().UnixMilli()
				f.UID = o.owner(f.Protocol, f.Local, f.Remote, f.LocalPort, f.RemotePort)
			}
			state.observe(f)
			f.dns = nil
		}
		seq++
		batch := Batch{r.id, seq, r.dropped.Load(), r.unacknowledged.Load(), facts}
		encoded, err := json.Marshal(batch)
		if err != nil || !o.sink(string(encoded)) {
			r.unacknowledged.Add(uint64(len(facts)))
		}
	}
}

func parsePacket(p []byte, upload bool) Fact {
	f := Fact{Observation: "packet", Upload: upload, Bytes: len(p), Packets: 1, UID: -1}
	bad := func(reason string) Fact { f.Unknown = reason; return f }
	if len(p) < 1 {
		return bad("empty packet")
	}
	var src, dst netip.Addr
	var offset, end int
	switch p[0] >> 4 {
	case 4:
		if len(p) < 20 {
			return bad("short IPv4 header")
		}
		offset = int(p[0]&15) * 4
		end = int(binary.BigEndian.Uint16(p[2:4]))
		if offset < 20 || end < offset || end > len(p) {
			return bad("invalid IPv4 length")
		}
		if end != len(p) {
			f.Unknown = "IP length differs from the observed TUN packet"
		}
		f.Protocol = int(p[9])
		src = netip.AddrFrom4([4]byte(p[12:16]))
		dst = netip.AddrFrom4([4]byte(p[16:20]))
		if binary.BigEndian.Uint16(p[6:8])&0x3fff != 0 {
			f.Unknown = "fragmented IPv4 packet"
		}
	case 6:
		if len(p) < 40 {
			return bad("short IPv6 header")
		}
		offset = 40
		end = 40 + int(binary.BigEndian.Uint16(p[4:6]))
		if end > len(p) || end == 40 {
			return bad("unsupported IPv6 length")
		}
		if end != len(p) {
			f.Unknown = "IP length differs from the observed TUN packet"
		}
		f.Protocol = int(p[6])
		src = netip.AddrFrom16([16]byte(p[8:24]))
		dst = netip.AddrFrom16([16]byte(p[24:40]))
		for n := 0; n < 8; n++ {
			switch f.Protocol {
			case 0, 43, 60:
				if offset+2 > end {
					return bad("short IPv6 extension")
				}
				next := int(p[offset])
				size := (int(p[offset+1]) + 1) * 8
				if offset+size > end {
					return bad("invalid IPv6 extension")
				}
				offset += size
				f.Protocol = next
			case 44:
				f.Unknown = "fragmented IPv6 packet"
				n = 8
			default:
				n = 8
			}
		}
	default:
		return bad("unsupported IP version")
	}
	if upload {
		f.Local = src.String()
		f.Remote = dst.String()
	} else {
		f.Local = dst.String()
		f.Remote = src.String()
	}
	if f.Unknown != "" {
		return f
	}
	if f.Protocol != 6 && f.Protocol != 17 {
		return bad("unsupported transport ownership")
	}
	min := 8
	if f.Protocol == 6 {
		min = 20
	}
	if offset+min > end {
		return bad("short transport header")
	}
	sport := binary.BigEndian.Uint16(p[offset:])
	dport := binary.BigEndian.Uint16(p[offset+2:])
	if upload {
		f.LocalPort = sport
		f.RemotePort = dport
	} else {
		f.LocalPort = dport
		f.RemotePort = sport
	}
	start := offset + 8
	if f.Protocol == 6 {
		h := int(p[offset+12]>>4) * 4
		if h < 20 || offset+h > end {
			return bad("invalid TCP header")
		}
		start = offset + h
	} else {
		length := int(binary.BigEndian.Uint16(p[offset+4:]))
		if length < 8 || offset+length > end {
			return bad("invalid UDP length")
		}
		end = offset + length
	}
	f.tuple = true
	if sport != 53 && dport != 53 {
		return f
	}
	if f.Protocol == 6 {
		if start == end {
			return f
		}
		if start+2 > end {
			return bad("DNS TCP reassembly unavailable")
		}
		length := int(binary.BigEndian.Uint16(p[start:]))
		start += 2
		if start+length != end {
			return bad("DNS TCP reassembly unavailable")
		}
	}
	if end-start > 4096 {
		return bad("DNS metadata size limit")
	}
	f.dns = append([]byte(nil), p[start:end]...)
	return f
}

// CanonicalName deliberately implements only strict ASCII DNS comparison v1.
// Unicode display names and malformed labels do not enter the candidate join.
func CanonicalName(raw string) string {
	if len(raw) > 0 && raw[len(raw)-1] == '.' {
		raw = raw[:len(raw)-1]
	}
	if len(raw) == 0 || len(raw) > 253 {
		return ""
	}
	b := []byte(raw)
	label := 0
	for i, c := range b {
		if c == '.' {
			if label == 0 || label > 63 {
				return ""
			}
			label = 0
			continue
		}
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_') {
			return ""
		}
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 32
		}
		label++
	}
	if label == 0 || label > 63 {
		return ""
	}
	return string(b)
}

type query struct {
	at  int64
	uid int32
}
type dnsState struct {
	queries     map[string]query
	answers     map[string]map[string]Candidate
	pruned      bool
	answerCount int
}

func (s *dnsState) observe(f *Fact) {
	// Bounded by explicit count and eligibility, never an unbounded DNS cache.
	if len(s.queries) > 4096 {
		clear(s.queries)
		s.pruned = true
	}
	if len(s.answers) > 8192 || s.answerCount >= 8192 {
		clear(s.answers)
		s.answerCount = 0
		s.pruned = true
	}
	if len(f.dns) > 0 {
		var m dnsmessage.Message
		if err := m.Unpack(f.dns); err == nil && len(m.Questions) == 1 && !m.Truncated {
			q := m.Questions[0]
			name := q.Name.String()
			canonical := CanonicalName(name)
			f.DNS = &DNS{ID: m.ID, Type: uint16(q.Type), Class: uint16(q.Class), Resolver: f.Remote, Name: name, Canonical: canonical, Response: m.Response, Code: int(m.RCode), QueryUID: -1}
			for _, rr := range m.Answers {
				var ip netip.Addr
				switch a := rr.Body.(type) {
				case *dnsmessage.AResource:
					ip = netip.AddrFrom4(a.A)
				case *dnsmessage.AAAAResource:
					ip = netip.AddrFrom16(a.AAAA)
				}
				if ip.IsValid() {
					f.DNS.Answers = append(f.DNS.Answers, DNSAnswer{rr.Header.Name.String(), ip.String(), rr.Header.TTL})
				}
			}
			keyBytes, _ := json.Marshal([]any{f.dnsScope(), f.Protocol, f.Local, f.Remote, f.LocalPort, f.RemotePort, m.ID, canonical, q.Type, q.Class})
			key := string(keyBytes)
			if canonical != "" && !m.Response {
				s.queries[key] = query{f.At, f.UID}
			} else if prior, ok := s.queries[key]; ok && f.At >= prior.at && f.At-prior.at <= 300000 {
				delete(s.queries, key)
				f.DNS.QueryUID = prior.uid
				f.DNS.QueryAt = prior.at
				f.DNS.Matched = true
				for _, rr := range m.Additionals {
					if opt, ok := rr.Body.(*dnsmessage.OPTResource); ok {
						for _, v := range opt.Options {
							if v.Code == 15 && len(v.Data) >= 2 {
								code := binary.BigEndian.Uint16(v.Data)
								f.DNS.ExtendedErrors = append(f.DNS.ExtendedErrors, code)
								if code == 15 {
									f.DNS.Blocked = true
								}
							}
						}
					}
				}
				owners := map[string]int64{canonical: 300000}
				for range m.Answers {
					for _, rr := range m.Answers {
						if c, ok := rr.Body.(*dnsmessage.CNAMEResource); ok {
							if ttl, eligible := owners[CanonicalName(rr.Header.Name.String())]; eligible {
								owners[CanonicalName(c.CNAME.String())] = min(ttl, int64(rr.Header.TTL)*1000)
							}
						}
					}
				}
				if m.RCode == 0 && !f.DNS.Blocked {
					for _, rr := range m.Answers {
						chainTTL, eligible := owners[CanonicalName(rr.Header.Name.String())]
						if !eligible || rr.Header.TTL == 0 || chainTTL == 0 {
							continue
						}
						var ip netip.Addr
						switch b := rr.Body.(type) {
						case *dnsmessage.AResource:
							ip = netip.AddrFrom4(b.A)
						case *dnsmessage.AAAAResource:
							ip = netip.AddrFrom16(b.AAAA)
						}
						if !ip.IsValid() || ip.IsUnspecified() {
							continue
						}
						key := f.dnsScope() + "/" + ip.String()
						if s.answers[key] == nil {
							s.answers[key] = make(map[string]Candidate)
						}
						if len(s.answers[key]) >= 256 {
							s.answerCount -= len(s.answers[key])
							clear(s.answers[key])
							s.pruned = true
						}
						ttl := min(int64(rr.Header.TTL)*1000, chainTTL)
						// Repeated answers for one question never add probability weight.
						if _, exists := s.answers[key][canonical]; !exists {
							s.answerCount++
						}
						s.answers[key][canonical] = Candidate{canonical, f.At, f.At + ttl, f.Remote}
					}
				}
			}
		} else {
			f.Unknown = "DNS metadata unavailable or truncated"
		}
	}
	for name, c := range s.answers[f.dnsScope()+"/"+f.Remote] {
		if c.AnswerAt <= f.At && f.At < c.Expires && f.RemotePort != 53 {
			f.Candidates = append(f.Candidates, c)
		} else if f.At >= c.Expires {
			delete(s.answers[f.dnsScope()+"/"+f.Remote], name)
			s.answerCount--
		}
	}
	sort.Slice(f.Candidates, func(i, j int) bool { return f.Candidates[i].Name < f.Candidates[j].Name })
	f.CandidateCoverage = "Observed DNS only; encrypted, cached or unobserved lookups remain unknown"
	if s.pruned {
		f.CandidateCoverage = "DNS metadata capacity exceeded; candidate set may be incomplete"
	}
}
