// Copyright (c) TailD contributors
// SPDX-License-Identifier: BSD-3-Clause
package main

import (
	"errors"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync/atomic"
	"syscall"
	"unsafe"

	"fyne.io/systray"
	"golang.org/x/sys/windows"
)

var desktopLaunching atomic.Bool
var desktopUser32 = windows.NewLazySystemDLL("user32.dll")
var desktopEnum = desktopUser32.NewProc("EnumWindows")
var desktopText = desktopUser32.NewProc("GetWindowTextW")
var desktopPID = desktopUser32.NewProc("GetWindowThreadProcessId")
var desktopVisible = desktopUser32.NewProc("IsWindowVisible")
var desktopIconic = desktopUser32.NewProc("IsIconic")
var desktopShow = desktopUser32.NewProc("ShowWindow")
var desktopForeground = desktopUser32.NewProc("SetForegroundWindow")
var desktopCallback = windows.NewCallback(findDesktopWindow)

type desktopSearch struct {
	path    string
	owner   *windows.SID
	window  uintptr
	pid     uint32
	process windows.Handle
	err     error
}

func configureDesktopAction() {
	// Secondary tap remains unset: the inherited library keeps its standard menu.
	systray.SetOnTapped(func() { go desktopAction(focusDesktopWindow, launchDesktop) })
}

func desktopAction(focus func() (bool, error), launch func() error) {
	found, err := focus()
	if err != nil {
		log.Printf("TailD desktop activation: %v", err)
		return
	}
	if found || !desktopLaunching.CompareAndSwap(false, true) {
		return
	}
	defer desktopLaunching.Store(false)
	// The windowless launcher owns collector/UI startup and normal close. Waiting
	// for its actual exit serializes rapid clicks without a timer or second owner.
	if err := launch(); err != nil {
		log.Printf("TailD desktop launch: %v", err)
	}
}

func launchDesktop() error {
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	command := exec.Command(filepath.Join(filepath.Dir(executable), "TailD", "TailD.exe"))
	command.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_NO_WINDOW}
	return command.Run()
}

func findDesktopWindow(window, param uintptr) uintptr {
	search := (*desktopSearch)(unsafe.Pointer(param))
	visible, _, _ := desktopVisible.Call(window)
	if visible == 0 {
		return 1
	}
	var title [128]uint16
	desktopText.Call(window, uintptr(unsafe.Pointer(&title[0])), uintptr(len(title)))
	if windows.UTF16ToString(title[:]) != "TailD · Network analytics" {
		return 1
	}
	var pid uint32
	desktopPID.Call(window, uintptr(unsafe.Pointer(&pid)))
	process, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pid)
	if err != nil {
		return 1
	}
	var name [32768]uint16
	size := uint32(len(name))
	if windows.QueryFullProcessImageName(process, 0, &name[0], &size) != nil ||
		!strings.EqualFold(filepath.Clean(windows.UTF16ToString(name[:size])), search.path) {
		windows.CloseHandle(process)
		return 1
	}
	var token windows.Token
	if err = windows.OpenProcessToken(process, windows.TOKEN_QUERY, &token); err != nil {
		windows.CloseHandle(process)
		search.err = errors.New("desktop owner unavailable")
		return 0
	}
	owner, err := token.GetTokenUser()
	token.Close()
	if err != nil {
		windows.CloseHandle(process)
		search.err = errors.New("desktop owner unavailable")
		return 0
	}
	if !owner.User.Sid.Equals(search.owner) {
		windows.CloseHandle(process)
		return 1
	}
	search.window = window
	search.pid = pid
	search.process = process
	return 0
}

func focusDesktopWindow() (bool, error) {
	executable, err := os.Executable()
	if err != nil {
		return false, err
	}
	owner, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		return false, err
	}
	search := desktopSearch{path: filepath.Join(filepath.Dir(executable), "TailD", "desktop", "TailD.Desktop.exe"), owner: owner.User.Sid}
	result, _, enumerationError := desktopEnum.Call(desktopCallback, uintptr(unsafe.Pointer(&search)))
	runtime.KeepAlive(&search)
	if search.process != 0 {
		defer windows.CloseHandle(search.process)
	}
	if search.err != nil {
		return false, search.err
	}
	if search.window == 0 {
		if result == 0 {
			return false, enumerationError
		}
		return false, nil
	}
	return activateDesktopWindow(search.window, search.pid)
}

func activateDesktopWindow(window uintptr, pid uint32) (bool, error) {
	var currentPID uint32
	desktopPID.Call(window, uintptr(unsafe.Pointer(&currentPID)))
	if currentPID != pid {
		return false, nil
	}
	if minimized, _, _ := desktopIconic.Call(window); minimized != 0 {
		desktopShow.Call(window, 9)
	}
	if focused, _, _ := desktopForeground.Call(window); focused == 0 {
		return true, errors.New("Windows denied foreground activation")
	}
	return true, nil
}
