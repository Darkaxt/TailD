// Copyright (c) TailD contributors
// SPDX-License-Identifier: BSD-3-Clause
package systray

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"unsafe"

	"golang.org/x/sys/windows"

	"tailscale.com/client/tailscale/apitype"
)

func TestTailDNotificationTargetsFollowNativeCompletion(t *testing.T) {
	q := notificationQueue{}
	q.pending = append(q.pending, fileNotification{path: `D:\Downloads\first (1).txt`})
	first := q.start()
	q.pending = append(q.pending, fileNotification{path: `D:\Downloads\second.txt`}, fileNotification{title: "Receive failed"})
	if q.start() != nil {
		t.Fatal("replaced an active notification")
	}
	if got := q.finish(0x405); got != first.path {
		t.Fatalf("wrong clicked file: %q", got)
	}
	q.start()
	if got := q.finish(0x404); got != "" {
		t.Fatal("dismissal revealed a file")
	}
	q.start()
	if got := q.finish(0x405); got != "" {
		t.Fatal("error notice revealed previous file")
	}
	if got := q.finish(0x405); got != "" {
		t.Fatal("duplicate click revealed a file")
	}
	q.pending = append(q.pending, fileNotification{path: "quiet"})
	q.start()
	if got := q.finish(0x403); got != "" {
		t.Fatal("quiet suppression revealed a file")
	}
}

func TestTailDReceiveNotificationUsesPublishedCollisionPath(t *testing.T) {
	dir := t.TempDir()
	name := "report, résumé #1.txt"
	if err := os.WriteFile(filepath.Join(dir, name), []byte("old"), 0600); err != nil {
		t.Fatal(err)
	}
	c := &testTaildropClient{body: "new", size: 3, files: []apitype.WaitingFile{{Name: name, Size: 3}}, deleteErr: true}
	var notices []fileNotification
	r := taildropReceiver{client: c, directory: func() (string, error) { return dir, nil }, notify: func(title, body, path string) {
		notices = append(notices, fileNotification{title: title, content: body, path: path})
	}}
	r.receive(context.Background(), true)
	want := filepath.Join(dir, "report, résumé #1 (1).txt")
	if len(notices) != 2 || notices[0].path != want || notices[1].path != "" {
		t.Fatalf("wrong save/ack targets: %#v", notices)
	}
	if b, err := os.ReadFile(want); err != nil || string(b) != "new" {
		t.Fatalf("not saved: %q %v", b, err)
	}
}

func TestTailDRevealRejectsMissingAndNonFileTargets(t *testing.T) {
	for _, path := range []string{"", "relative.txt", t.TempDir(), filepath.Join(t.TempDir(), "missing.txt")} {
		if err := revealSavedTaildropFile(path); err == nil {
			t.Fatalf("accepted %q", path)
		}
	}
}

func TestTailDNativeNotificationClickAndTrayForwarding(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	class, _ := windows.UTF16PtrFromString("SystrayClass")
	var forwarded int
	oldProc := windows.NewCallback(func(hwnd, message, wParam, lParam uintptr) uintptr {
		if message == 0x8000+45 || message == notificationCallbackMessage {
			forwarded++
			return 123
		}
		result, _, _ := notificationUser32.NewProc("DefWindowProcW").Call(hwnd, message, wParam, lParam)
		return result
	})
	type windowClass struct {
		size, style                        uint32
		proc                               uintptr
		classExtra, windowExtra            int32
		instance, icon, cursor, background uintptr
		menu, class                        *uint16
		smallIcon                          uintptr
	}
	wc := windowClass{proc: oldProc, class: class}
	wc.size = uint32(unsafe.Sizeof(wc))
	if atom, _, err := notificationUser32.NewProc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&wc))); atom == 0 {
		t.Fatal(err)
	}
	defer notificationUser32.NewProc("UnregisterClassW").Call(uintptr(unsafe.Pointer(class)), 0)
	hwnd, _, err := notificationUser32.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(class)), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
	if hwnd == 0 {
		t.Fatal(err)
	}
	destroy := func() { notificationUser32.NewProc("DestroyWindow").Call(hwnd) }
	defer destroy()
	selected := make(chan string, 1)
	previous := notificationReveal
	notificationReveal = func(path string) error { selected <- path; return nil }
	defer func() { notificationReveal = previous }()
	want := `D:\redirected downloads\résumé, report (1).txt`
	if err := queueWindowsNotification("File received", want, want); err != nil {
		t.Fatal(err)
	}
	// Start the submitted entry without asking the interactive user's shell to
	// display a test balloon. The actual Windows message must reach our subclass.
	notificationActions.Lock()
	notificationActions.queue.start()
	notificationActions.Unlock()
	send := notificationUser32.NewProc("SendMessageW")
	send.Call(hwnd, notificationCallbackMessage, notificationIconID, 0x405)
	if got := <-selected; got != want {
		t.Fatalf("selected %q instead of %q", got, want)
	}
	if got, _, _ := send.Call(hwnd, 0x8000+45, 0, 0); got != 123 {
		t.Fatal("lost original window procedure")
	}
	if got, _, _ := send.Call(hwnd, notificationCallbackMessage, notificationIconID, 0x205); got != 123 {
		t.Fatal("lost right click")
	}
	if forwarded != 2 {
		t.Fatalf("unexpected forwarding: %d", forwarded)
	}
	notificationActions.Lock()
	notificationActions.queue.active = &fileNotification{path: "old shell"}
	notificationActions.Unlock()
	send.Call(hwnd, notificationTaskbarCreated, 0, 0)
	notificationActions.Lock()
	if notificationActions.queue.active != nil {
		t.Error("Explorer restart retained stale activation")
	}
	notificationActions.Unlock()
	notificationActions.Lock()
	notificationActions.queue.pending = append(notificationActions.queue.pending, fileNotification{path: "shutdown"})
	notificationActions.Unlock()
	destroy()
	notificationActions.Lock()
	defer notificationActions.Unlock()
	if notificationActions.window != 0 || notificationActions.queue.active != nil || len(notificationActions.queue.pending) != 0 {
		t.Fatal("shutdown retained activation state")
	}
}

func TestTailDExplorerSelection(t *testing.T) {
	path := os.Getenv("TAILD_EXPLORER_TEST_FILE")
	if path == "" {
		t.Skip("Explicit synthetic-file Explorer integration check only")
	}
	if err := revealSavedTaildropFile(path); err != nil {
		t.Fatal(err)
	}
}
