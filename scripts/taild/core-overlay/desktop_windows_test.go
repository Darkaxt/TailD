// Copyright (c) TailD contributors
// SPDX-License-Identifier: BSD-3-Clause
package main

import (
	"errors"
	"os"
	"runtime"
	"sync/atomic"
	"testing"
	"unsafe"

	"golang.org/x/sys/windows"
)

func TestDesktopMinimizedIdentityAndRestore(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	class, _ := windows.UTF16PtrFromString("STATIC")
	// Escaped Unicode is intentional: the fixture must retain the native host's
	// actual title even when a broken ANSI build corrupts the source under test.
	title, _ := windows.UTF16PtrFromString("TailD \u00b7 Network analytics")
	position := int32(-32000)
	window, _, err := desktopUser32.NewProc("CreateWindowExW").Call(0x80,
		uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(title)), 0x10cf0000,
		uintptr(uint32(position)), uintptr(uint32(position)), 100, 40, 0, 0, 0, 0)
	if window == 0 {
		t.Fatal(err)
	}
	defer desktopUser32.NewProc("DestroyWindow").Call(window)
	desktopShow.Call(window, 6) // SW_MINIMIZE, real Windows state transition.
	if iconic, _, _ := desktopIconic.Call(window); iconic == 0 {
		t.Fatal("fixture not minimized")
	}
	path, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	owner, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		t.Fatal(err)
	}
	search := desktopSearch{path: path, owner: owner.User.Sid}
	desktopEnum.Call(desktopCallback, uintptr(unsafe.Pointer(&search)))
	runtime.KeepAlive(&search)
	if search.process != 0 {
		defer windows.CloseHandle(search.process)
	}
	if search.err != nil || search.window != window {
		var observed [128]uint16
		desktopText.Call(window, uintptr(unsafe.Pointer(&observed[0])), 128)
		visible, _, _ := desktopVisible.Call(window)
		var pid uint32
		desktopPID.Call(window, uintptr(unsafe.Pointer(&pid)))
		process, openErr := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pid)
		if openErr == nil {
			var name [32768]uint16
			size := uint32(len(name))
			queryErr := windows.QueryFullProcessImageName(process, 0, &name[0], &size)
			t.Logf("pid=%d self=%d path=%q expected=%q query=%v", pid, os.Getpid(), windows.UTF16ToString(name[:size]), path, queryErr)
			windows.CloseHandle(process)
		} else {
			t.Logf("pid=%d open=%v", pid, openErr)
		}
		t.Fatalf("existing minimized native window not matched: %v, title=%q visible=%d", search.err, windows.UTF16ToString(observed[:]), visible)
	}
	found, activationErr := activateDesktopWindow(search.window, search.pid)
	if !found {
		t.Fatalf("existing window lost: %v", activationErr)
	}
	if iconic, _, _ := desktopIconic.Call(window); iconic != 0 {
		t.Fatal("existing window remained minimized")
	}
	// Foreground restrictions must not convert an existing window into a launch.
	desktopAction(func() (bool, error) { return found, activationErr }, func() error { t.Fatal("existing window relaunched"); return nil })
}

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
