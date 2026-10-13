// Copyright (c) TailD contributors
// SPDX-License-Identifier: BSD-3-Clause
package main

import (
	"errors"
	"sync/atomic"
	"testing"
)

func TestDesktopActionFocusAndSerializedLaunch(t *testing.T) {
	var launches, focuses atomic.Int32
	entered, release, completed := make(chan struct{}), make(chan struct{}), make(chan struct{})
	missing := func() (bool, error) { return false, nil }
	launch := func() error { launches.Add(1); close(entered); <-release; return nil }
	go func() { desktopAction(missing, launch); close(completed) }()
	<-entered
	desktopAction(missing, func() error { launches.Add(1); return nil })
	desktopAction(func() (bool, error) { focuses.Add(1); return true, nil }, func() error { t.Error("existing window relaunched"); return nil })
	if launches.Load() != 1 || focuses.Load() != 1 {
		t.Fatal("launch/focus ownership not preserved")
	}
	close(release)
	<-completed
	desktopAction(missing, func() error { launches.Add(1); return nil })
	if launches.Load() != 2 {
		t.Fatal("closed launcher prevented a new launch")
	}
	desktopAction(func() (bool, error) { return false, errors.New("enumeration denied") }, func() error { t.Error("launched over unknown window state"); return nil })
}
