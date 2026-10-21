// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package androidvmtest

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

type nativeControlDFixture struct {
	mu                                      sync.Mutex
	rules                                   map[string]map[string]any
	filter, service, option                 int
	writes                                  int
	dropNext                                bool
	csv                                     string
	holdPolicy, resumePolicy, policyWaiting chan struct{}
	holdPath                                string
}

var nativeProviderLayout = flag.String("android.provider-layout", "", "optional large or landscape-large native provider/dashboard layout")

func newNativeControlDFixture() *nativeControlDFixture {
	f := &nativeControlDFixture{rules: map[string]map[string]any{
		"blocked.invalid":     {"PK": "blocked.invalid", "action": map[string]int{"do": 0, "status": 1}, "comment": "Existing incident", "group": 7},
		"unsupported.invalid": {"PK": "unsupported.invalid", "action": map[string]int{"do": 2, "status": 1}, "comment": "Leave this spoof rule unchanged", "via": "192.0.2.1", "group": 9},
	}, service: 1}
	var out strings.Builder
	writer := csv.NewWriter(&out)
	writer.Write([]string{"timestamp", "endpointId", "clientId", "profileId", "question", "action", "rrType", "trigger", "triggerValue", "answers", "answerCountryCode", "answerASN"})
	now := time.Now().UTC()
	row := func(at time.Time, client, question, action string) {
		writer.Write([]string{at.Format(time.RFC3339Nano), "endpoint", client, "profile", question, action, "A", "filter", "fixture, category", "192.0.2.2", "US", "64500"})
	}
	for i := 0; i < 121; i++ {
		row(now.Add(-time.Minute-time.Duration(i)*time.Second), "phone", "blocked.invalid", "0")
	}
	for i := 0; i < 2; i++ {
		row(now.Add(-10*time.Second), "phone", "blocked.invalid", "0")
	}
	row(now.Add(-72*time.Hour), "phone", "blocked.invalid", "0")
	row(now.Add(-5*time.Second), "phone", "allowed.invalid", "1")
	row(now.Add(-5*time.Second), "other", "other-client.invalid", "0")
	writer.Flush()
	f.csv = out.String()
	return f
}
func (f *nativeControlDFixture) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	var held chan struct{}
	if r.Method == "GET" && r.URL.Path == f.holdPath && f.holdPolicy != nil {
		held = f.holdPolicy
		f.holdPolicy = nil
		close(f.policyWaiting)
	}
	f.mu.Unlock()
	if held != nil {
		<-held
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	auth := r.Header.Get("Authorization")
	write := auth == "Bearer write-fixture"
	if auth != "Bearer read-fixture" && !write && auth != "Bearer other-write" && auth != "Bearer other-read" {
		http.Error(w, "synthetic denied", 403)
		return
	}
	if r.Method != "GET" && !write {
		http.Error(w, "synthetic write denied", 403)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	reply := func(body any) { json.NewEncoder(w).Encode(map[string]any{"success": true, "body": body}) }
	if r.Method == "GET" {
		switch r.URL.Path {
		case "/users":
			account := "account"
			if auth == "Bearer other-write" || auth == "Bearer other-read" {
				account = "different-account"
			}
			reply(map[string]any{"PK": account, "stats_endpoint": "fixture-region"})
		case "/profiles":
			reply(map[string]any{"profiles": []any{map[string]any{"PK": "profile", "name": "Shared test profile"}}})
		case "/devices":
			reply(map[string]any{"devices": []any{
				map[string]any{"PK": "endpoint", "name": "Emulator endpoint", "profile": map[string]string{"PK": "profile"}, "clients": []any{map[string]string{"PK": "phone", "name": "This emulator"}, map[string]string{"PK": "other", "name": "Other client"}}},
				map[string]any{"PK": "second", "name": "Another endpoint", "profile": map[string]string{"PK": "profile"}, "clients": []any{}},
			}})
		case "/profiles/profile/rules/all":
			keys := make([]string, 0, len(f.rules))
			for key := range f.rules {
				keys = append(keys, key)
			}
			sort.Strings(keys)
			rows := []any{}
			for _, key := range keys {
				rows = append(rows, f.rules[key])
			}
			reply(map[string]any{"rules": rows})
		case "/profiles/profile/filters":
			reply(map[string]any{"filters": []any{map[string]any{"PK": "ads", "name": "Fixture filter", "status": f.filter, "action": map[string]string{"lvl": "ads"}, "levels": []any{map[string]string{"name": "ads"}}}}})
		case "/profiles/profile/services":
			reply(map[string]any{"services": []any{map[string]any{"PK": "video", "name": "Fixture service", "action": map[string]int{"do": 0, "status": f.service}}}})
		case "/profiles/profile/options":
			reply(map[string]any{"options": []any{map[string]any{"PK": "block_rfc1918", "value": f.option}}})
		case "/profiles/options":
			reply(map[string]any{"options": []any{map[string]any{"PK": "block_rfc1918", "name": "Block private answers", "type": "toggle", "default_value": 0}}})
		case "/v2/activity-log/csv":
			w.Header().Set("Content-Type", "text/csv")
			from, errFrom := time.Parse(time.RFC3339Nano, r.URL.Query().Get("startTime"))
			until, errUntil := time.Parse(time.RFC3339Nano, r.URL.Query().Get("endTime"))
			if errFrom != nil || errUntil != nil || !from.Before(until) {
				http.Error(w, "invalid fixture window", 400)
				return
			}
			rows, _ := csv.NewReader(strings.NewReader(f.csv)).ReadAll()
			writer := csv.NewWriter(w)
			writer.Write(rows[0])
			for _, row := range rows[1:] {
				at, _ := time.Parse(time.RFC3339Nano, row[0])
				if !at.Before(from) && at.Before(until) {
					writer.Write(row)
				}
			}
			writer.Flush()
		default:
			http.NotFound(w, r)
		}
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "bad fixture form", 400)
		return
	}
	value := func(name string) int { n, _ := strconv.Atoi(r.Form.Get(name)); return n }
	switch {
	case r.URL.Path == "/profiles/profile/rules" && (r.Method == "POST" || r.Method == "PUT"):
		host := r.Form.Get("hostnames[]")
		group := value("group")
		if host == "blocked.invalid" && group != 7 {
			http.Error(w, "folder must survive", 400)
			return
		}
		f.rules[host] = map[string]any{"PK": host, "action": map[string]int{"do": value("do"), "status": value("status")}, "comment": r.Form.Get("comment"), "group": group}
	case strings.HasPrefix(r.URL.Path, "/profiles/profile/rules/") && r.Method == "DELETE":
		delete(f.rules, strings.TrimPrefix(r.URL.Path, "/profiles/profile/rules/"))
	case r.URL.Path == "/profiles/profile/filters/filter/ads":
		f.filter = value("status")
	case r.URL.Path == "/profiles/profile/services/video":
		f.service = value("status")
	case r.URL.Path == "/profiles/profile/options/block_rfc1918":
		f.option = value("status")
	default:
		http.NotFound(w, r)
		return
	}
	f.writes++
	if f.dropNext {
		f.dropNext = false
		connection, _, err := w.(http.Hijacker).Hijack()
		if err == nil {
			connection.Close()
		}
		return
	}
	reply(map[string]any{})
}

// Real native UI -> pinned fixture TLS -> provider-shaped reads and single-use
// writes -> private SQLite/Keystore -> process restart and explicit readback.
type controlDNativeStep struct{ name, class string }

func TestTailDControlDNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-initial", "TailDControlDInitialTest"}, {"tablet-restart", "TailDControlDRestartTest"}})
}

func TestTailDDashboardNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-dashboard", "TailDDashboardNativeTest"}, {"tablet-dashboard-restart", "TailDDashboardRestartTest"}, {"tablet-storage", "TailDDashboardStorageTest"}})
}

func TestTailDGeographyNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-map", "TailDGeographyNativeTest"}, {"tablet-map", "TailDGeographyNativeTest"}})
}

func runControlDNative(t *testing.T, steps []controlDNativeStep) {
	if *taildTestAPK == "" {
		t.Skip("explicit instrumentation APK required")
	}
	if !strings.HasPrefix(*adbSerial, "emulator-") {
		t.Fatal("owned emulator required")
	}
	run := func(args ...string) string {
		t.Helper()
		out, err := exec.Command(*adbPath, append([]string{"-s", *adbSerial}, args...)...).CombinedOutput()
		if err != nil {
			t.Fatalf("fixture adb %v: %v: %s", args, err, out)
		}
		return string(out)
	}
	if strings.TrimSpace(run("shell", "getprop", "ro.kernel.qemu")) != "1" {
		t.Fatal("physical targets forbidden")
	}
	for _, apk := range []string{*apkPath, *taildTestAPK} {
		run("install", "-r", "-t", apk)
	}
	fixture := newNativeControlDFixture()
	if len(steps) > 0 && steps[0].class == "TailDGeographyNativeTest" {
		fixture.csv = strings.Replace(fixture.csv, ",US,64500", ",US;DE,64500", 1)
		fixture.csv = strings.Replace(fixture.csv, ",US,64500", ",,64500", 1)
	}
	server := httptest.NewTLSServer(fixture)
	defer server.Close()
	defer func() {
		fixture.mu.Lock()
		if fixture.resumePolicy != nil {
			close(fixture.resumePolicy)
			fixture.resumePolicy = nil
		}
		fixture.mu.Unlock()
	}()
	parsed, _ := url.Parse(server.URL)
	mapping := "tcp:" + parsed.Port()
	run("reverse", mapping, mapping)
	t.Cleanup(func() { run("reverse", "--remove", mapping) })
	digest := sha256.Sum256(server.Certificate().Raw)
	const pkg = "io.github.darkaxt.taildns"
	var appAccess *appAccessNativeFixture
	if len(steps) > 0 && strings.HasPrefix(steps[0].class, "TailDAppAccess") {
		appAccess = newAppAccessNativeFixture(t, run)
	}
	// A fresh owned emulator has no VPN grant; MainActivity's ordinary preparation
	// dialog would obscure every native fixture action. This is test setup only.
	run("shell", "appops", "set", pkg, "ACTIVATE_VPN", "allow")
	for _, step := range steps {
		run("shell", "am", "force-stop", pkg)
		run("shell", "wm", "user-rotation", "lock", "0")
		if strings.HasPrefix(step.name, "phone-") {
			run("shell", "wm", "size", "1080x2400")
			run("shell", "wm", "density", "480")
			run("shell", "cmd", "uimode", "night", "no")
		} else {
			run("shell", "wm", "size", "1680x1800")
			run("shell", "wm", "density", "320")
			run("shell", "cmd", "uimode", "night", "yes")
		}
		if step.class == "TailDGeographyNativeTest" {
			// Override the ordinary tablet fixture's dark baseline: each map
			// workflow proves a real light-to-dark transition on a fresh process.
			run("shell", "cmd", "uimode", "night", "no")
		}
		landscape := "false"
		font := "1.0"
		if *nativeProviderLayout != "" {
			if *nativeProviderLayout != "large" && *nativeProviderLayout != "landscape-large" {
				t.Fatal("unsupported provider layout")
			}
			font = "1.5"
			if strings.HasPrefix(step.name, "phone-") && *nativeProviderLayout == "large" {
				run("shell", "wm", "size", "1236x2745")
			}
			if *nativeProviderLayout == "landscape-large" {
				landscape = "true"
				run("shell", "wm", "user-rotation", "lock", "1")
			}
		}
		run("shell", "settings", "put", "system", "font_scale", font)
		cmd := exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "instrument", "-w", "-r", "-e", "class", "com.tailscale.ipn.taild."+step.class,
			"-e", "app_access_profile", strconv.Itoa(*appAccessProfile),
			"-e", "taild_fixture", "true", "-e", "landscape", landscape, "-e", "fixture_url", server.URL, "-e", "fixture_cert", hex.EncodeToString(digest[:]), pkg+".test/androidx.test.runner.AndroidJUnitRunner")
		stdout, err := cmd.StdoutPipe()
		if err != nil {
			t.Fatal(err)
		}
		cmd.Stderr = cmd.Stdout
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		seen := map[string]bool{}
		phases := make(chan string, 1) // Each native phase waits for its acknowledgment.
		exited := make(chan struct{})
		var result struct {
			output              string
			processErr, scanErr error
		}
		go func() {
			var output strings.Builder
			scanner := bufio.NewScanner(stdout)
			for scanner.Scan() {
				line := scanner.Text()
				fmt.Fprintln(&output, line)
				if strings.HasPrefix(line, "INSTRUMENTATION_STATUS: taild_failure=") {
					t.Log(line)
				}
				const marker = "INSTRUMENTATION_STATUS: taild_phase="
				if strings.HasPrefix(line, marker) {
					phases <- strings.TrimSpace(strings.TrimPrefix(line, marker))
				}
			}
			result.output = output.String()
			result.scanErr = scanner.Err()
			if result.scanErr != nil {
				// Observe command completion even when an unexpected oversized diagnostic
				// line exceeds Scanner's budget; an unread pipe would deadlock Wait.
				io.Copy(io.Discard, stdout)
			}
			result.processErr = cmd.Wait()
			close(exited)
			close(phases)
		}()
		observed := false
		defer func() {
			if !observed {
				exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "force-stop", pkg).Run()
				<-exited
			}
		}()
		for phase := range phases {
			t.Logf("native %s phase %s", step.name, phase)
			if appAccess != nil {
				appAccess.phase(phase)
			}
			seen[phase] = true
			var phaseErr error
			fixture.mu.Lock()
			switch phase {
			case "hold-policy", "hold-old-policy", "hold-history":
				fixture.holdPath = "/profiles/profile/rules/all"
				if phase == "hold-old-policy" {
					fixture.holdPath = "/profiles/profile/options"
				}
				if phase == "hold-history" {
					fixture.holdPath = "/v2/activity-log/csv"
				}
				fixture.resumePolicy = make(chan struct{})
				fixture.holdPolicy = fixture.resumePolicy
				fixture.policyWaiting = make(chan struct{})
			case "release-policy", "release-history":
				close(fixture.resumePolicy)
				fixture.resumePolicy = nil
			case "assert-read-only-dashboard":
				if fixture.writes != 0 {
					phaseErr = fmt.Errorf("Dashboard performed %d provider writes", fixture.writes)
				}
			case "stale-policy":
				fixture.filter = 1 - fixture.filter
			case "drop-next-write":
				fixture.dropNext = true
			case "assert-after-unknown", "assert-after-restart", "assert-after-reconcile":
				if fixture.writes != 9 {
					phaseErr = fmt.Errorf("expected 9 explicit writes, got %d", fixture.writes)
				}
			}
			fixture.mu.Unlock()
			if phase == "policy-waiting" || phase == "history-waiting" {
				select {
				case <-fixture.policyWaiting:
				case <-exited:
					t.Fatalf("Native instrumentation exited while awaiting a fixture request: %v\n%s", result.processErr, result.output)
				}
			}
			if phase == "switch-theme" {
				run("shell", "cmd", "uimode", "night", "yes")
			}
			if strings.HasPrefix(phase, "capture-") && *taildCaptureHelper != "" {
				out, err := exec.CommandContext(context.Background(), "python", "-B", *taildCaptureHelper, "--serial", *adbSerial, "--output-dir", filepath.Join(*taildCaptureDir, step.name), "--prefix", phase).CombinedOutput()
				if err != nil {
					phaseErr = fmt.Errorf("native capture: %w", err)
				}
				t.Logf("capture %s/%s: %s", step.name, phase, out)
			}
			port := strings.TrimSpace(run("forward", "tcp:0", "localabstract:taild-r37-native"))
			ack, err := net.Dial("tcp", "127.0.0.1:"+port)
			if err == nil {
				result := byte(1)
				if phaseErr != nil {
					result = 0
					t.Error(phaseErr)
				}
				_, err = ack.Write([]byte{result})
				if err == nil {
					var receipt [1]byte
					_, err = io.ReadFull(ack, receipt[:])
					if err == nil && receipt[0] != result {
						err = fmt.Errorf("invalid native receipt")
					}
				}
				ack.Close()
			}
			if err != nil {
				t.Errorf("native phase %s acknowledgment: %v", phase, err)
				run("shell", "am", "force-stop", pkg)
			}
			run("forward", "--remove", "tcp:"+port)
		}
		<-exited
		observed = true
		if result.processErr != nil || result.scanErr != nil || !strings.Contains(result.output, "OK (1 test)") || strings.Contains(result.output, "FAILURES") {
			t.Fatalf("Control D native %s: %v %v\n%s", step.name, result.processErr, result.scanErr, result.output)
		}
		required := []string{"capture-recent", "capture-reconciled", "assert-after-restart", "assert-after-reconcile"}
		if appAccess != nil {
			required = appAccessRequired(step.class)
		}
		if step.class == "TailDGeographyNativeTest" {
			required = []string{"capture-map-light", "capture-map-drilldown", "capture-map-dark", "capture-map-empty", "capture-map-scope", "assert-read-only-dashboard"}
		}
		if step.name == "phone-initial" {
			required = []string{"capture-recent", "capture-editor", "stale-policy", "drop-next-write", "assert-after-unknown", "capture-unknown"}
		}
		if step.name == "phone-dashboard" {
			required = []string{"capture-dashboard", "capture-drilldown", "capture-dashboard-dark", "assert-read-only-dashboard"}
		}
		if step.name == "tablet-storage" {
			required = nil
		}
		if step.name == "tablet-dashboard-restart" {
			required = []string{"capture-dashboard-restart", "assert-read-only-dashboard"}
		}
		for _, phase := range required {
			if !seen[phase] {
				t.Fatalf("missing native Control D phase %s", phase)
			}
		}
		t.Logf("Control D native %s passed", step.name)
	}
}
