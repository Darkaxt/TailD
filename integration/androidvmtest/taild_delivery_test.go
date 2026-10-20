// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package androidvmtest

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"tailscale.com/ipn/store/mem"
	"tailscale.com/tsnet"
	"tailscale.com/tstest/integration/testcontrol"
)

var deliveryAPK = flag.String("android.delivery-apk", "", "independently verified production-signed candidate")
var baselineAPK = flag.String("android.baseline-apk", "", "independently verified TailDNS upgrade origin")
var deliveryReceipt = flag.String("android.delivery-receipt", "", "independent android_release.py verification JSON")
var harnessAPK = flag.String("android.delivery-harness-apk", "", "self-targeted harness application APK")
var harnessTestAPK = flag.String("android.delivery-harness-test-apk", "", "matching self-targeted instrumentation APK")
var deliveryReadHelper = flag.String("android.delivery-read-helper", "", "private READ-only credential socket helper (optional)")
var deliveryEndpoint = flag.String("android.delivery-endpoint", "", "existing live READ endpoint display name")
var deliveryProfile = flag.String("android.delivery-profile", "", "existing live READ profile display name")

var deliveryFinalizeOnly = flag.Bool("android.delivery-finalize", false, "finish cleanup and TalkBack on the retained candidate; prior migration and recovery evidence is separate")
var deliveryUICorrection = flag.Bool("android.delivery-ui-correction", false, "verify the bounded device-list/navigation/search correction on the normally signed candidate")

var deliveryResumeCandidate = flag.Bool("android.delivery-resume-candidate", false, "continue recovery/read/accessibility on the retained verified candidate; does not establish the origin upgrade")
var deliveryOriginFolderPrepared = flag.Bool("android.delivery-origin-folder-prepared", false, "resume the previously verified origin TailDrop directory grant")
var deliveryOriginIntroSeen = flag.Bool("android.delivery-origin-intro-seen", false, "resume preserved TailDNS origin after its verified onboarding tap")

func TestTailDProductionDelivery(t *testing.T) {
	if *deliveryAPK == "" {
		t.Skip("explicit verified signed delivery inputs required")
	}
	if *deliveryFinalizeOnly && !*deliveryResumeCandidate {
		t.Fatal("finalization requires the retained candidate")
	}
	if !strings.HasPrefix(*adbSerial, "emulator-") {
		t.Fatal("production delivery tests require the owned emulator")
	}
	var receipt struct {
		Verified bool   `json:"verified"`
		Code     int64  `json:"version_code"`
		APK      string `json:"apk_sha256"`
		Source   string `json:"source"`
		Package  string `json:"package"`
		Signer   string `json:"signer_sha256"`
	}
	data, err := os.ReadFile(*deliveryReceipt)
	if err != nil {
		t.Fatal(err)
	}
	if err = json.Unmarshal(data, &receipt); err != nil {
		t.Fatal(err)
	}
	data, err = os.ReadFile(*deliveryAPK)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(data)
	if !receipt.Verified || receipt.APK != hex.EncodeToString(sum[:]) || len(receipt.Source) != 40 || receipt.Package != "io.github.darkaxt.taildns" || receipt.Signer != "dcd0ede91eb7e0ed88a72b5289f84f8d4a61ccc22707f36378e15540b99d32e1" {
		t.Fatal("candidate bytes do not match independent verification")
	}
	run := func(args ...string) string {
		t.Helper()
		out, err := exec.Command(*adbPath, append([]string{"-s", *adbSerial}, args...)...).CombinedOutput()
		if err != nil {
			t.Fatalf("delivery adb %v: %v: %s", args, err, out)
		}
		return string(out)
	}
	if strings.TrimSpace(run("shell", "getprop", "ro.kernel.qemu")) != "1" {
		t.Fatal("physical targets forbidden")
	}
	const pkg = "io.github.darkaxt.taildns"
	const harness = "io.github.darkaxt.taild.delivery"
	// No uninstall/reset fallback. A mismatched existing app requires reviewed owned-test cleanup.
	installations := []string{*harnessAPK, *harnessTestAPK}
	if !*deliveryResumeCandidate {
		installations = append([]string{*baselineAPK}, installations...)
	}
	for _, apk := range installations {
		if apk == "" {
			t.Fatal("complete delivery inputs required")
		}
		run("install", "-r", "-t", apk)
	}
	run("shell", "appops", "set", pkg, "ACTIVATE_VPN", "allow")
	run("shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS")
	run("shell", "wm", "size", "1236x2745")
	run("shell", "wm", "density", "480")
	run("shell", "settings", "put", "system", "font_scale", "1.0")
	run("shell", "cmd", "uimode", "night", "no")
	oldServices := strings.TrimSpace(run("shell", "settings", "get", "secure", "enabled_accessibility_services"))
	oldAccessibility := strings.TrimSpace(run("shell", "settings", "get", "secure", "accessibility_enabled"))
	restore := func() {
		if oldServices == "null" {
			run("shell", "settings", "delete", "secure", "enabled_accessibility_services")
		} else {
			run("shell", "settings", "put", "secure", "enabled_accessibility_services", oldServices)
		}
		if oldAccessibility == "null" {
			run("shell", "settings", "delete", "secure", "accessibility_enabled")
		} else {
			run("shell", "settings", "put", "secure", "accessibility_enabled", oldAccessibility)
		}
	}
	t.Cleanup(restore)
	derp := runDERPAndSTUN(t, "127.0.0.1")
	control := &testcontrol.Server{DERPMap: derp, AllOnline: true, AllNodesSameUser: true, MagicDNSDomain: "taild.test"}
	server := httptest.NewServer(control)
	defer server.Close()
	control.ExplicitBaseURL = server.URL
	parsed, _ := url.Parse(server.URL)
	for _, port := range []string{parsed.Port(), fmt.Sprint(derp.Regions[1].Nodes[0].DERPPort)} {
		mapping := "tcp:" + port
		run("reverse", mapping, mapping)
		t.Cleanup(func() { run("reverse", "--remove", mapping) })
	}
	peerName := "taild-delivery-peer-" + parsed.Port()
	peer := &tsnet.Server{Dir: t.TempDir(), ControlURL: server.URL, Hostname: peerName, Ephemeral: true, Store: new(mem.Store), Logf: t.Logf}
	defer peer.Close()
	fixtureStatus, err := peer.Up(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	args := []string{"-s", *adbSerial, "shell", "am", "instrument", "-w", "-r", "-e", "class", "io.github.darkaxt.taild.delivery.TailDDeliveryTest#productionUpgradeRecoveryAndAccessibility", "-e", "taild_delivery", "true", "-e", "control_url", server.URL, "-e", "source_revision", receipt.Source}
	args = append(args, "-e", "candidate_code", fmt.Sprint(receipt.Code), "-e", "peer_name", peerName)
	if *deliveryUICorrection {
		args = append(args, "-e", "ui_correction", "true")
		for _, profile := range fixtureStatus.User {
			if profile.DisplayName != "" {
				args = append(args, "-e", "owner_name", profile.DisplayName)
				break
			}
		}
	}
	if *deliveryResumeCandidate {
		args = append(args, "-e", "resume_candidate", "true")
	}
	if *deliveryFinalizeOnly {
		args = append(args, "-e", "finalize_only", "true")
	}
	if *deliveryOriginFolderPrepared {
		args = append(args, "-e", "origin_folder_prepared", "true")
	}
	if *deliveryOriginIntroSeen {
		args = append(args, "-e", "origin_intro_seen", "true")
	}
	if *deliveryReadHelper != "" {
		if *deliveryEndpoint == "" || *deliveryProfile == "" {
			t.Fatal("explicit existing READ scope required")
		}
		args = append(args, "-e", "live_read", "true", "-e", "endpoint_name", *deliveryEndpoint, "-e", "profile_name", *deliveryProfile)
	}
	args = append(args, harness+".test/androidx.test.runner.AndroidJUnitRunner")
	cmd := exec.Command(*adbPath, args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	cmd.Stderr = cmd.Stdout
	if err = cmd.Start(); err != nil {
		t.Fatal(err)
	}
	waited := false
	defer func() {
		if !waited {
			exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "force-stop", harness).Run()
			cmd.Wait()
		}
	}()
	if *taildCaptureDir != "" {
		if err := os.MkdirAll(*taildCaptureDir, 0700); err != nil {
			t.Fatal(err)
		}
	}
	var output strings.Builder
	seen := map[string]int{}
	var initialID, initialMachine string
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 4096), 2*1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		fmt.Fprintln(&output, line)
		if strings.HasPrefix(line, "INSTRUMENTATION_STATUS: taild_rendered_controls=") && *taildCaptureDir != "" {
			text := strings.TrimPrefix(line, "INSTRUMENTATION_STATUS: taild_rendered_controls=")
			var tree any
			if json.Unmarshal([]byte(text), &tree) != nil {
				t.Error("invalid actual rendered hierarchy")
			}
			if err := os.WriteFile(filepath.Join(*taildCaptureDir, "production-rendered-controls.json"), []byte(text), 0600); err != nil {
				t.Error(err)
			}
		}
		const marker = "INSTRUMENTATION_STATUS: taild_phase="
		if !strings.HasPrefix(line, marker) {
			continue
		}
		phase := strings.TrimSpace(strings.TrimPrefix(line, marker))
		seen[phase]++
		t.Logf("production delivery phase %s", phase)
		if phase == "read-credential-ready" {
			out, err := exec.Command("python", "-B", *deliveryReadHelper, "--serial", *adbSerial, "--socket", "taild-r37-release-read").CombinedOutput()
			if err != nil {
				t.Errorf("READ credential transport failed: %v", err)
				run("shell", "am", "force-stop", harness)
			} else {
				t.Logf("%s", out)
			}
			continue
		}
		var phaseErr error
		switch phase {
		case "delivery-verified":
			if *deliveryReadHelper != "" {
				out, auditErr := exec.Command("python", "-B", *deliveryReadHelper, "--serial", *adbSerial, "--socket", "taild-r37-release-read", "--audit-logs").CombinedOutput()
				if auditErr != nil {
					phaseErr = fmt.Errorf("private READ log audit failed: %v", auditErr)
				} else {
					t.Log(strings.TrimSpace(string(out)))
				}
			}

		case "baseline-ready", "recovery-baseline", "assert-node-continuity":
			if strings.TrimSpace(run("shell", "settings", "get", "secure", "always_on_vpn_app")) != pkg {
				phaseErr = fmt.Errorf("always-on package association was not retained")
				break
			}
			lc, err := peer.LocalClient()
			if err != nil {
				phaseErr = err
				break
			}
			status, err := lc.Status(context.Background())
			if err != nil {
				phaseErr = err
				break
			}
			if len(status.Peer) != 1 {
				phaseErr = fmt.Errorf("expected exactly one isolated Android peer, got %d", len(status.Peer))
				break
			}
			matched := 0
			for _, target := range status.Peer {
				for _, node := range control.AllNodes() {
					// Testcontrol retains the old and candidate keys during rotation.
					// Compare the live peer's exact current key, not every staged entry.
					if node.StableID == target.ID && node.Key == target.PublicKey {
						matched++
						if phase == "baseline-ready" || phase == "recovery-baseline" {
							initialID = string(node.StableID)
							initialMachine = node.Machine.String()
						} else if string(node.StableID) != initialID || node.Machine.String() != initialMachine {
							phaseErr = fmt.Errorf("in-place replacement changed node or machine identity")
						}
					}
				}
			}
			if initialID == "" || matched != 1 {
				phaseErr = fmt.Errorf("expected one exact current stable peer, got %d", matched)
			}
		case "upgrade", "reinstall":
			run("install", "-r", *deliveryAPK)
		case "rejected-downgrade":
			out, err := exec.Command(*adbPath, "-s", *adbSerial, "install", "-r", *baselineAPK).CombinedOutput()
			if err == nil || !strings.Contains(string(out), "INSTALL_FAILED_VERSION_DOWNGRADE") {
				phaseErr = fmt.Errorf("expected nondestructive version downgrade rejection: %v: %s", err, out)
			}
		case "receive-ready":
			lc, err := peer.LocalClient()
			if err != nil {
				phaseErr = err
				break
			}
			status, err := lc.Status(context.Background())
			if err != nil {
				phaseErr = err
				break
			}
			for _, target := range status.Peer {
				body := "taild-delivery-private-body"
				phaseErr = lc.PushFile(context.Background(), target.ID, int64(len(body)), "taild-delivery.txt", strings.NewReader(body))
			}
		case "assert-saved-file":
			if strings.TrimSpace(run("shell", "cat", "/sdcard/TailDDelivery/taild-delivery.txt")) != "taild-delivery-private-body" {
				phaseErr = fmt.Errorf("actual document save did not preserve the fixture file")
			}
		case "enable-talkback":
			services := oldServices
			if services == "null" {
				services = ""
			}
			if services != "" {
				services += ":"
			}
			services += "com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService"
			run("shell", "settings", "put", "secure", "enabled_accessibility_services", services)
			run("shell", "settings", "put", "secure", "accessibility_enabled", "1")
		case "disable-talkback":
			restore()
		case "capture-talkback":
			dump := run("shell", "dumpsys", "accessibility")
			section := ""
			if start := strings.Index(dump, "Bound services:"); start >= 0 {
				section = dump[start:]
				if end := strings.Index(section, "Enabled services:"); end >= 0 {
					section = section[:end]
				}
			}
			if *taildCaptureDir != "" {
				if err := os.WriteFile(filepath.Join(*taildCaptureDir, "production-accessibility-bound.txt"), []byte(section), 0600); err != nil {
					t.Error(err)
				}
			}
			// This Android image prints only the service label in the bound section.
			// Bind that record to the sole enabled and independently resolved component.
			enabled := strings.TrimSpace(run("shell", "settings", "get", "secure", "enabled_accessibility_services"))
			resolved := run("shell", "cmd", "package", "query-services", "--brief", "-a", "android.accessibilityservice.AccessibilityService", "-p", "com.google.android.marvin.talkback")
			bound := strings.Contains(section, "Service[label=TalkBack,") && strings.Contains(section, "FEEDBACK_SPOKEN") &&
				enabled == "com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService" &&
				strings.Contains(resolved, "com.google.android.marvin.talkback/.TalkBackService")
			if *taildCaptureDir != "" {
				if err := os.WriteFile(filepath.Join(*taildCaptureDir, "production-accessibility-identity.txt"), []byte(enabled+"\n"+resolved), 0600); err != nil {
					t.Error(err)
				}
			}
			if !bound {
				phaseErr = fmt.Errorf("TalkBack is not actually bound")
			}
		}
		if strings.HasPrefix(phase, "capture-") && *taildCaptureHelper != "" {
			out, err := exec.Command("python", "-B", *taildCaptureHelper, "--serial", *adbSerial, "--output-dir", *taildCaptureDir, "--prefix", phase).CombinedOutput()
			if err != nil {
				phaseErr = fmt.Errorf("delivery capture: %w", err)
			}
			t.Logf("capture %s: %s", phase, out)
		}
		port := strings.TrimSpace(run("forward", "tcp:0", "localabstract:taild-r37-delivery"))
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
					err = fmt.Errorf("incorrect delivery acknowledgment")
				}
			}
			ack.Close()
		}
		run("forward", "--remove", "tcp:"+port)
		if err != nil {
			t.Errorf("delivery acknowledgment: %v", err)
			run("shell", "am", "force-stop", harness)
		}
	}
	err = cmd.Wait()
	waited = true
	result := output.String()
	if err != nil || scanner.Err() != nil || !strings.Contains(result, "OK (1 test)") || strings.Contains(result, "FAILURES") {
		t.Fatalf("production native delivery: %v %v\n%s", err, scanner.Err(), result)
	}
	required := []string{"assert-node-continuity", "rejected-downgrade", "reinstall", "capture-talkback", "delivery-verified"}
	if *deliveryUICorrection {
		required = []string{"baseline-ready", "upgrade", "assert-node-continuity", "capture-ui-phone-light", "capture-ui-phone-dark", "capture-ui-rail-dark", "capture-ui-rail-light", "rejected-downgrade", "reinstall", "delivery-verified"}
	} else if *deliveryFinalizeOnly {
		required = []string{"capture-talkback", "delivery-verified"}
	} else if *deliveryResumeCandidate {
		required = append(required, "resumed-candidate", "recovery-baseline")
	} else {
		required = append(required, "baseline-ready", "upgrade", "receive-ready", "assert-saved-file")
	}
	for _, phase := range required {
		if seen[phase] == 0 {
			t.Fatalf("missing production acceptance phase %s", phase)
		}
	}
	if *deliveryUICorrection {
		t.Log("Normally signed correction verified: in-place identity, owner-free list, Android self icon, phone/rail marks and DNS search/clear across live system themes, rejected downgrade and exact reinstall")
		return
	}
	if *deliveryFinalizeOnly {
		t.Log("Retained production-signed candidate cleanup, log audit and TalkBack session verified; migration/recovery assertions belong to their earlier evidence")
		return
	}
	t.Log("Actual production signer, selected-mode continuity, retained data, rejected downgrade, exact reinstall, external VPN broadcasts and TalkBack focus session verified on owned emulator")
	if *deliveryReadHelper != "" {
		t.Log("Live READ access and retained provider vault verified through the production UI; no Write credential used")
	}
}
