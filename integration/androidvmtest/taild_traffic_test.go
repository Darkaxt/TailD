// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package androidvmtest

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"golang.org/x/net/dns/dnsmessage"
	_ "tailscale.com/feature/capture"
	"tailscale.com/ipn/store/mem"
	"tailscale.com/tailcfg"
	"tailscale.com/tsnet"
	"tailscale.com/tstest/integration/testcontrol"
)

var trafficExpectedAVD = flag.String("android.traffic-expected-avd", "", "exact owned AVD name for native traffic acceptance")

func TestTailDTrafficNativeUI(t *testing.T) {
	if *taildTestAPK == "" {
		t.Skip("explicit native APK fixtures required")
	}
	if !strings.HasPrefix(*adbSerial, "emulator-") || *apkPath == "" || *appAccessFixtures == "" {
		t.Fatal("owned emulator/APK/fixture required")
	}
	run := func(args ...string) string {
		t.Helper()
		out, err := exec.Command(*adbPath, append([]string{"-s", *adbSerial}, args...)...).CombinedOutput()
		if err != nil {
			t.Fatalf("adb %v: %v: %s", args, err, out)
		}
		return string(out)
	}
	if *trafficExpectedAVD == "" || strings.TrimSpace(run("shell", "getprop", "ro.boot.qemu.avd_name")) != *trafficExpectedAVD {
		t.Fatal("owned AVD identity mismatch")
	}
	const pkg = "io.github.darkaxt.taildns"
	// This audit uses the public active-VPN owner API and must work without Shizuku.
	pidOut, pidErr := exec.Command(*adbPath, "-s", *adbSerial, "shell", "pidof", "shizuku_server").CombinedOutput()
	if pidErr == nil {
		pid := strings.TrimSpace(string(pidOut))
		if !regexp.MustCompile(`^\d+$`).MatchString(pid) {
			t.Fatal("ambiguous owned Shizuku process")
		}
		identity := run("shell", "ps", "-p", pid, "-o", "UID,ARGS")
		if !regexp.MustCompile(`(?m)^\s*2000\s+shizuku_server\s*$`).MatchString(identity) {
			t.Fatalf("Shizuku process identity mismatch: %s", identity)
		}
		run("shell", "kill", pid)
	}

	for _, path := range []string{*apkPath, *taildTestAPK, filepath.Join(*appAccessFixtures, "one.apk"), filepath.Join(*appAccessFixtures, "two.apk")} {
		run("install", "-r", "-t", path)
	}
	usageState := run("shell", "appops", "get", pkg, "GET_USAGE_STATS")
	usageOriginal := "default"
	if match := regexp.MustCompile(`GET_USAGE_STATS: (allow|ignore|deny|default|foreground)`).FindStringSubmatch(usageState); len(match) == 2 {
		usageOriginal = match[1]
	} else if !strings.Contains(usageState, "No operations") {
		t.Fatalf("unrecognized owned Usage Access state: %s", usageState)
	}
	defer run("shell", "appops", "set", pkg, "GET_USAGE_STATS", usageOriginal)
	run("shell", "appops", "set", pkg, "ACTIVATE_VPN", "allow")
	run("shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS")
	derp := runDERPAndSTUN(t, "127.0.0.1")
	control := &testcontrol.Server{DERPMap: derp, RequireAuthKey: authKey, AllOnline: true, AllNodesSameUser: true, MagicDNSDomain: "taild.test", DNSConfig: &tailcfg.DNSConfig{Proxied: true}}
	server := httptest.NewServer(control)
	defer server.Close()
	control.ExplicitBaseURL = server.URL
	u, _ := url.Parse(server.URL)
	for _, port := range []string{u.Port(), strconv.Itoa(derp.Regions[1].Nodes[0].DERPPort)} {
		mapping := "tcp:" + port
		run("reverse", mapping, mapping)
		t.Cleanup(func() { run("reverse", "--remove", mapping) })
	}
	peer := &tsnet.Server{Dir: t.TempDir(), ControlURL: server.URL, AuthKey: authKey, Hostname: "taild-test-peer", Ephemeral: true, Store: new(mem.Store), Logf: t.Logf}
	defer peer.Close()
	status, err := peer.Up(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	client, err := peer.LocalClient()
	if err != nil {
		t.Fatal(err)
	}
	if *taildCaptureDir != "" {
		if err := os.MkdirAll(*taildCaptureDir, 0700); err != nil {
			t.Fatal(err)
		}
		capture, err := client.StreamDebugCapture(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		file, err := os.Create(filepath.Join(*taildCaptureDir, "isolated-peer-diagnostic.pcap"))
		if err != nil {
			capture.Close()
			t.Fatal(err)
		}
		copied := make(chan struct{})
		go func() { defer close(copied); io.Copy(file, capture) }()
		defer func() { capture.Close(); <-copied; file.Close() }()
	}
	ip := status.TailscaleIPs[0].String()
	control.AddDNSRecords(tailcfg.DNSRecord{Name: "alpha.taild.test", Type: "A", Value: ip}, tailcfg.DNSRecord{Name: "beta.taild.test", Type: "A", Value: ip})
	dnsSocket, err := peer.ListenPacket("udp", ip+":53")
	if err != nil {
		t.Fatal(err)
	}
	defer dnsSocket.Close()
	go func() {
		buffer := make([]byte, 4096)
		for {
			n, addr, err := dnsSocket.ReadFrom(buffer)
			if err != nil {
				return
			}
			var request dnsmessage.Message
			if request.Unpack(buffer[:n]) != nil || len(request.Questions) != 1 {
				continue
			}
			response := dnsmessage.Message{Header: dnsmessage.Header{ID: request.ID, Response: true, RCode: dnsmessage.RCodeNameError}, Questions: request.Questions,
				Additionals: []dnsmessage.Resource{{Header: dnsmessage.ResourceHeader{Name: dnsmessage.MustNewName("."), Type: dnsmessage.TypeOPT, Class: 1232}, Body: &dnsmessage.OPTResource{Options: []dnsmessage.Option{{Code: 15, Data: []byte{0, 15}}}}}}}
			encoded, err := response.Pack()
			if err == nil {
				_, _ = dnsSocket.WriteTo(encoded, addr)
			}
		}
	}()
	listener, err := peer.Listen("tcp", ":18080")
	if err != nil {
		t.Fatal(err)
	}
	uploadReceived := make(chan struct{})
	release := make(chan struct{})
	finish := make(chan struct{})
	completed := make(chan struct{})
	var uploadOnce, releaseOnce, finishOnce, completedOnce sync.Once
	t.Cleanup(func() { releaseOnce.Do(func() { close(release) }); finishOnce.Do(func() { close(finish) }) })
	httpServer := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/traffic/native" || r.Method != "POST" {
			http.Error(w, "fixture target", 400)
			return
		}
		body, err := io.ReadAll(r.Body)
		if err != nil || len(body) != 8192 {
			http.Error(w, "fixture body", 400)
			return
		}
		for i, v := range body {
			if v != byte(i%251) {
				http.Error(w, "fixture bytes", 400)
				return
			}
		}
		uploadOnce.Do(func() { close(uploadReceived) })
		<-release
		w.Header().Set("Content-Length", "32769")
		_, _ = w.Write([]byte(strings.Repeat("x", 32768)))
		w.(http.Flusher).Flush()
		<-finish
		_, _ = w.Write([]byte("z"))
		completedOnce.Do(func() { close(completed) })
	})}
	defer func() {
		releaseOnce.Do(func() { close(release) })
		finishOnce.Do(func() { close(finish) })
		httpServer.Close()
	}()
	go func() { t.Logf("fixture HTTP listener ended: %v", httpServer.Serve(listener)) }()
	var directRequests atomic.Int64
	directServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/app-access/direct" {
			http.Error(w, "fixture", 400)
			return
		}
		directRequests.Add(1)
		w.WriteHeader(200)
	}))
	defer directServer.Close()
	directURL, _ := url.Parse(directServer.URL)
	defer run("shell", "svc", "wifi", "enable")

	run("shell", "am", "force-stop", pkg)
	run("shell", "wm", "size", "1080x2400")
	run("shell", "wm", "density", "480")
	run("shell", "settings", "put", "system", "font_scale", "1.0")
	run("shell", "cmd", "uimode", "night", "no")
	seen := map[string]bool{}
	for _, className := range []string{"TailDTrafficNativeTest", "TailDTrafficRestartNativeTest", "TrafficStoreIntegrationTest"} {
		run("shell", "am", "force-stop", pkg)
		cmd := exec.Command(*adbPath, "-s", *adbSerial, "shell", "am", "instrument", "-w", "-r", "-e", "class", "com.tailscale.ipn.taild."+className, "-e", "taild_fixture", "true", pkg+".test/androidx.test.runner.AndroidJUnitRunner")
		stdout, err := cmd.StdoutPipe()
		if err != nil {
			t.Fatal(err)
		}
		cmd.Stderr = cmd.Stdout
		if err = cmd.Start(); err != nil {
			t.Fatal(err)
		}
		var output strings.Builder
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
			t.Logf("phase %s", phase)
			switch phase {
			case "login-ready":
				run("shell", "am", "broadcast", "-a", pkg+".integration.LOGIN", "-n", pkg+"/com.tailscale.ipn.IPNReceiver", "--include-stopped-packages", "--es", "control_url", server.URL, "--es", "auth_key", authKey)
			case "traffic-start", "network-probe":
				if phase == "network-probe" {
					found := false
					for _, node := range control.AllNodes() {
						if node.Key == status.Self.PublicKey {
							continue
						}
						for _, prefix := range node.Addresses {
							if !prefix.Addr().Is4() {
								continue
							}
							found = true
							result, err := client.Ping(context.Background(), prefix.Addr(), tailcfg.PingPeerAPI)
							if err != nil || result == nil || result.Err != "" {
								run("shell", "am", "force-stop", pkg)
								t.Fatalf("Post-transition data-path readiness: %+v %v", result, err)
							}
							t.Logf("post-transition PeerAPI HTTP data path ready: %+v", result)
						}
					}
					if !found {
						run("shell", "am", "force-stop", pkg)
						t.Fatal("Android node absent at transition")
					}
				}
				out := run("shell", "am", "broadcast", "-n", "io.github.darkaxt.taild.fixture.one/io.github.darkaxt.taild.fixture.TrafficReceiver", "--include-stopped-packages", "--es", "url", "http://"+ip+":18080/traffic/native", "--ez", "resolver_block", strconv.FormatBool(phase == "traffic-start"))
				if !strings.Contains(out, "STARTED") {
					t.Error(out)
				}
			case "traffic-release":
				<-uploadReceived
				releaseOnce.Do(func() { close(release) })
			case "traffic-finish":
				finishOnce.Do(func() { close(finish) })
				<-completed
			case "usage-accounting":
				run("shell", "appops", "set", pkg, "GET_USAGE_STATS", "allow")
				if out := run("shell", "dumpsys", "netstats", "--poll"); !strings.Contains(out, "Forced poll") {
					t.Fatalf("owned OS accounting poll: %s", out)
				}
			case "usage-revoke":
				run("shell", "appops", "set", pkg, "GET_USAGE_STATS", "ignore")
			case "network-mobile":
				run("shell", "svc", "wifi", "disable")
			case "network-restore":
				run("shell", "svc", "wifi", "enable")
			case "direct-route":
				out := run("shell", "am", "broadcast", "-n", "io.github.darkaxt.taild.fixture.one/io.github.darkaxt.taild.fixture.ProbeReceiver", "--include-stopped-packages", "--es", "url", "http://10.0.2.2:"+directURL.Port()+"/app-access/direct")
				if !strings.Contains(out, "HTTP_200") || directRequests.Load() != 1 {
					t.Errorf("direct-route receipt: %s count=%d", out, directRequests.Load())
				}
			case "layout-phone-large":
				run("shell", "settings", "put", "system", "font_scale", "1.5")
			case "layout-tablet":
				run("shell", "wm", "size", "1200x1920")
				run("shell", "wm", "density", "160")
			case "layout-landscape":
				run("shell", "wm", "size", "1920x1200")
			case "layout-phone":
				run("shell", "wm", "size", "1080x2400")
				run("shell", "wm", "density", "480")
				run("shell", "settings", "put", "system", "font_scale", "1.0")
			case "traffic-reinstall":
				run("install", "-r", "-t", filepath.Join(*appAccessFixtures, "one.apk"))
			case "switch-theme":
				run("shell", "cmd", "uimode", "night", "yes")
			case "traffic-close":
				run("shell", "am", "broadcast", "-n", "io.github.darkaxt.taild.fixture.one/io.github.darkaxt.taild.fixture.TrafficReceiver", "--es", "operation", "close")
			default:
				if strings.HasPrefix(phase, "capture-") && *taildCaptureHelper != "" {
					out, err := exec.Command("python", "-B", *taildCaptureHelper, "--serial", *adbSerial, "--output-dir", *taildCaptureDir, "--prefix", phase).CombinedOutput()
					if err != nil {
						t.Errorf("capture: %v: %s", err, out)
					}
				}
			}
			port := strings.TrimSpace(run("forward", "tcp:0", "localabstract:taild-r37-native"))
			ack, err := net.Dial("tcp", "127.0.0.1:"+port)
			if err != nil {
				t.Fatal(err)
			}
			_, err = ack.Write([]byte{1})
			if err != nil {
				t.Fatal(err)
			}
			var receipt [1]byte
			if _, err = io.ReadFull(ack, receipt[:]); err != nil || receipt[0] != 1 {
				t.Fatalf("phase ack %v", err)
			}
			ack.Close()
			run("forward", "--remove", "tcp:"+port)
		}
		err = cmd.Wait()
		if err != nil || scanner.Err() != nil || !strings.Contains(output.String(), "OK (1 test)") {
			t.Fatalf("real native traffic: %v: %v\n%s", err, scanner.Err(), output.String())
		}
	}
	for _, phase := range []string{"login-ready", "traffic-start", "traffic-release", "traffic-finish", "capture-traffic-apps", "capture-traffic-details", "usage-accounting", "usage-revoke", "document-exported", "switch-theme", "capture-traffic-dark", "network-mobile", "network-probe", "network-restore", "direct-route", "layout-phone-large", "capture-traffic-large", "layout-tablet", "capture-traffic-tablet", "layout-landscape", "capture-traffic-landscape", "layout-phone", "traffic-reinstall", "retained-for-restart", "capture-traffic-restarted-cleared", "traffic-close"} {
		if !seen[phase] {
			t.Fatalf("missing phase %s", phase)
		}
	}
}
