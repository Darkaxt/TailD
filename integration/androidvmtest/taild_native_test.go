// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package androidvmtest

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	_ "tailscale.com/feature/taildrop"
	"testing"

	"tailscale.com/ipn/store/mem"
	"tailscale.com/tsnet"
	"tailscale.com/tstest/integration/testcontrol"
)

var taildTestAPK = flag.String("android.test-apk", "", "TailD instrumentation APK; enables isolated native UI test")
var taildCaptureHelper = flag.String("android.capture-helper", "", "installed host-only Android screenshot helper")
var taildCaptureDir = flag.String("android.capture-dir", "", "task-owned host screenshot output directory")
var taildViewport = flag.String("android.viewport", "", "one named viewport for focused native diagnostics; blank runs the full matrix")

// This test never uses a real tailnet, provider credential or physical device.
// It reuses the inherited testcontrol/DERP boundary with the actual native APK.
func TestTailDNativeUI(t *testing.T) {
	if *taildTestAPK == "" {
		t.Skip("set android.test-apk for isolated native acceptance")
	}
	if *apkPath == "" || !strings.HasPrefix(*adbSerial, "emulator-") {
		t.Fatal("explicit APK and emulator serial required")
	}
	run := func(args ...string) string {
		t.Helper()
		out, err := exec.Command(*adbPath, append([]string{"-s", *adbSerial}, args...)...).CombinedOutput()
		if err != nil {
			t.Fatalf("isolated adb %v: %v\n%s", args, err, out)
		}
		return string(out)
	}
	if strings.TrimSpace(run("shell", "getprop", "ro.kernel.qemu")) != "1" {
		t.Fatal("target is not an emulator")
	}
	const pkg = "io.github.darkaxt.taildns"
	for _, apk := range []string{*apkPath, *taildTestAPK} {
		if _, err := os.Stat(apk); err != nil {
			t.Fatal(err)
		}
		run("install", "-r", "-t", apk)
	}
	run("shell", "appops", "set", pkg, "ACTIVATE_VPN", "allow")
	run("shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS")
	derp := runDERPAndSTUN(t, "127.0.0.1")
	control := &testcontrol.Server{DERPMap: derp, RequireAuthKey: authKey, AllOnline: true, AllNodesSameUser: true, MagicDNSDomain: "taild.test"}
	server := httptest.NewServer(control)
	defer server.Close()
	control.ExplicitBaseURL = server.URL
	u, err := url.Parse(server.URL)
	if err != nil {
		t.Fatal(err)
	}
	for _, port := range []string{u.Port(), strconv.Itoa(derp.Regions[1].Nodes[0].DERPPort)} {
		mapping := "tcp:" + port
		run("reverse", mapping, mapping)
		t.Cleanup(func() { run("reverse", "--remove", mapping) })
	}
	peer := &tsnet.Server{Dir: t.TempDir(), ControlURL: server.URL, AuthKey: authKey,
		Hostname: "taild-test-peer", Ephemeral: true, Store: new(mem.Store), Logf: t.Logf}
	defer peer.Close()
	fixtureStatus, err := peer.Up(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	verifiedViewports := 0
	for _, size := range []struct{ name, pixels, density, font, landscape, night, layoutOnly string }{
		{"phone-360", "1080x2400", "480", "1.0", "false", "no", "false"},
		{"phone-412-large", "1236x2745", "480", "1.5", "false", "no", "false"},
		{"tablet-840", "1680x1800", "320", "1.0", "false", "no", "false"},
		{"phone-landscape-dark", "1080x2400", "480", "1.0", "true", "yes", "true"},
		{"tablet-landscape-dark-large", "1680x1800", "320", "1.5", "true", "yes", "true"},
	} {
		if *taildViewport != "" && *taildViewport != size.name {
			continue
		}
		// Each viewport starts a new app process. Credentials here are public
		// testcontrol fixtures, supplied after that process declares readiness.
		run("shell", "am", "force-stop", pkg)
		run("shell", "wm", "size", size.pixels)
		run("shell", "wm", "density", size.density)
		run("shell", "settings", "put", "system", "font_scale", size.font)
		run("shell", "cmd", "uimode", "night", size.night)
		run("shell", "input", "keyevent", "82")
		cmd := exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "instrument", "-w", "-r", "-e", "class",
			"com.tailscale.ipn.taild.TailDNativeConnectionTest", "-e", "taild_fixture", "true",
			"-e", "landscape", size.landscape, "-e", "layout_only", size.layoutOnly,
			"-e", "fixture_peer_key", fixtureStatus.Self.PublicKey.String(),
			"-e", "require_restart_gap", strconv.FormatBool(verifiedViewports > 0),
			pkg+".test/androidx.test.runner.AndroidJUnitRunner")
		stdout, err := cmd.StdoutPipe()
		if err != nil {
			t.Fatal(err)
		}
		cmd.Stderr = cmd.Stdout
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		var output strings.Builder
		seen := make(map[string]bool)
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			fmt.Fprintln(&output, line)
			const marker = "INSTRUMENTATION_STATUS: taild_phase="
			if !strings.HasPrefix(line, marker) {
				continue
			}
			phase := strings.TrimSpace(strings.TrimPrefix(line, marker))
			seen[phase] = true
			forward, forwardErr := exec.Command(*adbPath, "-s", *adbSerial, "forward", "tcp:0", "localabstract:taild-r37-native").CombinedOutput()
			if forwardErr != nil {
				t.Errorf("test handshake forward: %v: %s", forwardErr, forward)
				run("shell", "am", "force-stop", pkg)
				continue
			}
			port := strings.TrimSpace(string(forward))
			var phaseErr error
			if phase == "login-ready" {
				out, err := exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "broadcast", "-a", pkg+".integration.LOGIN",
					"-n", pkg+"/com.tailscale.ipn.IPNReceiver", "--include-stopped-packages", "--es", "control_url", server.URL,
					"--es", "auth_key", authKey).CombinedOutput()
				if err != nil {
					phaseErr = fmt.Errorf("fixture login dispatch: %w: %s", err, out)
				}
			} else if phase == "switch-theme" {
				night := "yes"
				if size.night == "yes" {
					night = "no"
				}
				out, err := exec.Command(*adbPath, "-s", *adbSerial, "shell", "cmd", "uimode", "night", night).CombinedOutput()
				if err != nil {
					phaseErr = fmt.Errorf("live system theme change: %w: %s", err, out)
				}
			} else if phase == "receive-ready" {
				// Direct auth-key resume must not leave two node keys for one
				// stable node in the fixture control plane. Such a map cannot
				// validate a transfer and must fail before attempting it.
				identities := make(map[int64]bool)
				for _, node := range control.AllNodes() {
					id := int64(node.ID)
					if identities[id] {
						phaseErr = fmt.Errorf("fixture has duplicate keys for node %d", id)
					}
					identities[id] = true
				}
				lc, err := peer.LocalClient()
				if err == nil && phaseErr == nil {
					status, statusErr := lc.Status(context.Background())
					err = statusErr
					if err == nil {
						if len(status.Peer) != 1 {
							err = fmt.Errorf("expected exactly one isolated Android peer, got %d", len(status.Peer))
						} else {
							for _, target := range status.Peer {
								body := "taild-a1-private-payload"
								err = lc.PushFile(context.Background(), target.ID, int64(len(body)), "taild-native-"+size.name+".txt", strings.NewReader(body))
							}
						}
					}
				}
				if err != nil {
					phaseErr = err
				}
			} else if strings.HasPrefix(phase, "capture-") && *taildCaptureHelper != "" {
				if *taildCaptureDir == "" {
					phaseErr = fmt.Errorf("capture directory required")
				} else {
					out, err := exec.Command("python", "-B", *taildCaptureHelper, "--serial", *adbSerial,
						"--output-dir", filepath.Join(*taildCaptureDir, size.name), "--prefix", phase).CombinedOutput()
					phaseErr = err
					t.Logf("capture %s/%s: %s", size.name, phase, out)
				}
			}
			ack, err := net.Dial("tcp", "127.0.0.1:"+port)
			if err == nil {
				result := byte(1)
				if phaseErr != nil {
					result = 0
					t.Errorf("phase %s: %v", phase, phaseErr)
				}
				_, err = ack.Write([]byte{result})
				if err == nil {
					var receipt [1]byte
					_, err = io.ReadFull(ack, receipt[:])
					if err == nil && receipt[0] != result {
						err = fmt.Errorf("invalid phase receipt")
					}
				}
				ack.Close()
			}
			if err != nil {
				t.Errorf("test phase acknowledgment: %v", err)
				run("shell", "am", "force-stop", pkg)
			}
			run("forward", "--remove", "tcp:"+port)
		}
		err = cmd.Wait()
		result := output.String()
		if err != nil || scanner.Err() != nil {
			t.Fatalf("native instrumentation: %v, scan %v\n%s", err, scanner.Err(), result)
		}
		if !strings.Contains(result, "OK (1 test)") || strings.Contains(result, "FAILURES") {
			t.Fatalf("native acceptance %s:\n%s", size.name, result)
		}
		required := []string{"login-ready", "capture-connection", "capture-preferences", "capture-activity", "capture-taildrop"}
		if size.layoutOnly != "true" {
			required = append(required, "receive-ready")
		} else {
			required = append(required, "switch-theme", "capture-theme-changed")
		}
		for _, phase := range required {
			if !seen[phase] {
				t.Fatalf("native acceptance omitted phase %s", phase)
			}
		}
		t.Logf("native acceptance %s passed", size.name)
		verifiedViewports++
	}
	if verifiedViewports == 0 {
		t.Fatal("no matching native viewport")
	}
	t.Log(fmt.Sprintf("verified native TailD against isolated %s, no production tailnet", server.URL))
}
