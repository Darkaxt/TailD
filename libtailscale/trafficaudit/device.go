// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package trafficaudit

import "github.com/tailscale/wireguard-go/tun"

// Device delegates the entire descriptor contract and observes successful transfers only.
type Device struct {
	tun.Device
	Observer *Observer
	Scope    Scope
}

func (d *Device) Read(slab []byte, packets []tun.ReadPacket) (int, error) {
	n, err := d.Device.Read(slab, packets)
	for _, p := range packets[:n] {
		d.Observer.Observe(slab[p.Offset:p.Offset+p.Size], true, d.Scope)
	}
	return n, err
}

func (d *Device) Write(bufs [][]byte, offset int) (int, error) {
	n, err := d.Device.Write(bufs, offset)
	// The pinned NativeTun's non-vnetHdr path (used by Android's supplied
	// unmonitored FD) returns bytes, unlike Device's documented packet-count
	// convention. Preserve that actual return contract. Successful calls account
	// for every supplied packet; a mixed/partial failure cannot identify which
	// packet succeeded, so its returned bytes remain explicitly unassigned.
	total := 0
	for _, p := range bufs {
		total += len(p) - offset
	}
	if err == nil && n == total {
		for _, p := range bufs {
			d.Observer.Observe(p[offset:], false, d.Scope)
		}
	} else if n > 0 {
		d.Observer.observeUnassignedWrite(n, d.Scope)
	}
	return n, err
}
