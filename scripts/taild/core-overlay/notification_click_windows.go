// Copyright (c) TailD contributors
// SPDX-License-Identifier: BSD-3-Clause
package systray

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"unsafe"

	"golang.org/x/sys/windows"
)

// fyne.io/systray v1.12.2 has no balloon activation callback. Subclass only
// our existing window, forwarding every library message to its original proc.
// No new notification-area icon or independent window/message pump is created.
const notificationWake = 0x8000 + 46
const notificationCallbackMessage = 0x400 + 1
const notificationIconID = 100

type fileNotification struct{ title, content, path string }
type notificationQueue struct {
	pending []fileNotification
	active  *fileNotification
}

func (q *notificationQueue) start() *fileNotification {
	if q.active != nil || len(q.pending) == 0 {
		return nil
	}
	n := q.pending[0]
	q.pending[0] = fileNotification{}
	q.pending = q.pending[1:]
	q.active = &n
	return q.active
}

func (q *notificationQueue) finish(event uintptr) string {
	if q.active == nil {
		return ""
	}
	path := ""
	if event == 0x405 {
		path = q.active.path
	} // NIN_BALLOONUSERCLICK
	q.active = nil
	return path
}

var notificationActions struct {
	sync.Mutex
	window, original uintptr
	queue            notificationQueue
}
var notificationSetProc = notificationUser32.NewProc("SetWindowLongPtrW")
var notificationCallProc = notificationUser32.NewProc("CallWindowProcW")
var notificationPost = notificationUser32.NewProc("PostMessageW")
var notificationProc uintptr
var notificationReveal = revealSavedTaildropFile
var notificationTaskbarCreated uintptr

func init() {
	notificationProc = windows.NewCallback(notificationWindowProc)
	name, _ := windows.UTF16PtrFromString("TaskbarCreated")
	notificationTaskbarCreated, _, _ = notificationUser32.NewProc("RegisterWindowMessageW").Call(uintptr(unsafe.Pointer(name)))
}

func queueWindowsNotification(title, content, path string) error {
	window, err := notificationWindow()
	if err != nil {
		return err
	}
	notificationActions.Lock()
	defer notificationActions.Unlock()
	if notificationActions.window == 0 {
		// GWLP_WNDPROC is a signed pointer-sized -4. This distribution is amd64.
		original, _, e := notificationSetProc.Call(window, ^uintptr(3), notificationProc)
		if original == 0 {
			return fmt.Errorf("notification activation setup: %v", e)
		}
		notificationActions.window = window
		notificationActions.original = original
	}
	if notificationActions.window != window {
		return fmt.Errorf("notification window changed")
	}
	notificationActions.queue.pending = append(notificationActions.queue.pending, fileNotification{title, content, path})
	if ok, _, e := notificationPost.Call(window, notificationWake, 0, 0); ok == 0 {
		notificationActions.queue.pending = notificationActions.queue.pending[:len(notificationActions.queue.pending)-1]
		return fmt.Errorf("notification dispatch: %v", e)
	}
	return nil
}

func notificationWindowProc(window, message, wParam, lParam uintptr) uintptr {
	notificationActions.Lock()
	original := notificationActions.original
	if message == notificationTaskbarCreated && notificationTaskbarCreated != 0 {
		// Explorer has discarded the old icon and balloons. Drop their activation
		// targets before forwarding the library's icon recreation; new receives
		// can notify normally without depending on a missing terminal callback.
		notificationActions.queue = notificationQueue{}
	}
	if message == notificationWake {
		n := notificationActions.queue.start()
		notificationActions.Unlock()
		if n != nil {
			if err := showWindowsNotificationAt(window, n.title, n.content); err != nil {
				log.Printf("Windows notification: %v", err)
				completeWindowsNotification(window, 0x403)
			}
		}
		return 0
	}
	if message == notificationCallbackMessage && wParam == notificationIconID &&
		(lParam == 0x403 || lParam == 0x404 || lParam == 0x405) {
		notificationActions.Unlock()
		completeWindowsNotification(window, lParam)
		return 0
	}
	if message == 0x82 { // WM_NCDESTROY: remove our subclass in reverse order.
		notificationSetProc.Call(window, ^uintptr(3), original)
		notificationActions.window = 0
		notificationActions.original = 0
		notificationActions.queue = notificationQueue{}
	}
	notificationActions.Unlock()
	result, _, _ := notificationCallProc.Call(original, window, message, wParam, lParam)
	return result
}

func completeWindowsNotification(window, event uintptr) {
	notificationActions.Lock()
	path := notificationActions.queue.finish(event)
	notificationActions.Unlock()
	if path != "" {
		go func() {
			if err := notificationReveal(path); err != nil {
				log.Printf("TailDrop reveal: %v", err)
				if e := queueWindowsNotification("Cannot show received file", "The file may have been moved or removed, or Explorer is unavailable.", ""); e != nil {
					log.Printf("TailDrop reveal notice: %v", e)
				}
			}
		}()
	}
	// Native hide/timeout/click are mutually exclusive terminal events. Advance
	// after the callback returns; never overwrite an active balloon or use a timer.
	if ok, _, err := notificationPost.Call(window, notificationWake, 0, 0); ok == 0 {
		log.Printf("Windows notification queue wake: %v", err)
	}
}

func (menu *Menu) sendTaildropNotification(title, content, path string) {
	if err := queueWindowsNotification(title, content, path); err != nil {
		log.Printf("Windows notification: %v", err)
	}
}

var notificationOle32 = windows.NewLazySystemDLL("ole32.dll")
var notificationInitialize = notificationOle32.NewProc("CoInitializeEx")
var notificationUninitialize = notificationOle32.NewProc("CoUninitialize")
var notificationFree = notificationOle32.NewProc("CoTaskMemFree")
var notificationParse = windows.NewLazySystemDLL("shell32.dll").NewProc("SHParseDisplayName")
var notificationSelect = windows.NewLazySystemDLL("shell32.dll").NewProc("SHOpenFolderAndSelectItems")

func revealSavedTaildropFile(path string) error {
	if !filepath.IsAbs(path) {
		return fmt.Errorf("received path is not absolute")
	}
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return fmt.Errorf("received file is no longer a regular file")
	}
	name, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return err
	}
	// COM initialization and Shell use must stay on the same native thread.
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	hr, _, _ := notificationInitialize.Call(0, 2) // COINIT_APARTMENTTHREADED
	if int32(hr) < 0 {
		return fmt.Errorf("Explorer COM initialization: %#x", hr)
	}
	defer notificationUninitialize.Call()
	var item uintptr
	hr, _, _ = notificationParse.Call(uintptr(unsafe.Pointer(name)), 0, uintptr(unsafe.Pointer(&item)), 0, 0)
	runtime.KeepAlive(name)
	if int32(hr) < 0 {
		return fmt.Errorf("Explorer file lookup: %#x", hr)
	}
	defer notificationFree.Call(item)
	// cidl=0 means a fully specified single item: open its parent and select it.
	// PIDLs avoid command-line parsing and never execute the received file.
	hr, _, _ = notificationSelect.Call(item, 0, 0, 0)
	if int32(hr) < 0 {
		return fmt.Errorf("Explorer file selection: %#x", hr)
	}
	return nil
}
