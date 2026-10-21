// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package androidvmtest

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"testing"
)

var appAccessFixtures = flag.String("android.appaccess-fixtures", "", "exact task-owned fixture build directory")
var appAccessProfile = flag.Int("android.appaccess-profile", 0, "task-owned secondary Android profile")

func TestTailDAppAccessNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-appaccess", "TailDAppAccessNativeTest"}, {"tablet-appaccess-restart", "TailDAppAccessRestartNativeTest"}})
}

func TestTailDAppAccessFailureNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-appaccess-failure", "TailDAppAccessFailureNativeTest"}})
}

func TestTailDAppAccessRebootNativeUI(t *testing.T) {
	runControlDNative(t, []controlDNativeStep{{"phone-appaccess-reboot", "TailDAppAccessRebootNativeTest"}})
}

type appAccessNativeFixture struct {
	t      *testing.T
	run    func(...string) string
	server *httptest.Server
	mu     sync.Mutex
	seen   map[string]int
	next   int
	uids   map[string]int
	twoAPK string
}

func newAppAccessNativeFixture(t *testing.T, run func(...string) string) *appAccessNativeFixture {
	t.Helper()
	if *appAccessFixtures == "" || *appAccessProfile <= 0 {
		t.Fatal("owned fixture directory/profile are required")
	}
	data, err := os.ReadFile(filepath.Join(*appAccessFixtures, "fixtures.json"))
	if err != nil {
		t.Fatal(err)
	}
	var manifest struct {
		Schema          int
		PolicyDexSHA256 string `json:"policy_dex_sha256"`
		Fixtures        []struct{ Package, APK, SHA256 string }
	}
	if err := json.Unmarshal(data, &manifest); err != nil || manifest.Schema != 1 || len(manifest.Fixtures) != 3 {
		t.Fatalf("invalid app fixture manifest: %v", err)
	}
	f := &appAccessNativeFixture{t: t, run: run, seen: map[string]int{}, uids: map[string]int{}}
	for _, asset := range manifest.Fixtures {
		if asset.Package != "io.github.darkaxt.taild.fixture.one" && asset.Package != "io.github.darkaxt.taild.fixture.two" && asset.Package != "io.github.darkaxt.taild.fixture.other" {
			t.Fatal("unexpected fixture identity")
		}
		contents, err := os.ReadFile(asset.APK)
		if err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(contents)
		if hex.EncodeToString(digest[:]) != asset.SHA256 {
			t.Fatal("fixture APK digest changed")
		}
		if strings.HasSuffix(asset.Package, ".two") {
			f.twoAPK = asset.APK
		}
		for _, user := range []int{0, *appAccessProfile} {
			output := run("shell", "cmd", "package", "list", "packages", "-U", "--user", strconv.Itoa(user), asset.Package)
			match := regexp.MustCompile(`(?m)^package:` + regexp.QuoteMeta(asset.Package) + ` uid:(\d+)\s*$`).FindStringSubmatch(output)
			if len(match) != 2 {
				t.Fatalf("missing fixture package/profile: %s/%d", asset.Package, user)
			}
			uid, _ := strconv.Atoi(match[1])
			if uid/100000 != user || uid%100000 < 10000 {
				t.Fatal("invalid fixture UID")
			}
			f.uids[fmt.Sprintf("%d/%s", user, asset.Package)] = uid
		}
	}
	for _, user := range []int{0, *appAccessProfile} {
		if f.uid(user, "one") != f.uid(user, "two") || f.uid(user, "one") == f.uid(user, "other") {
			t.Fatal("shared-UID fixture identity mismatch")
		}
	}
	dex := filepath.Join(*appAccessFixtures, "dex", "classes.dex")
	contents, err := os.ReadFile(dex)
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(contents)
	if hex.EncodeToString(digest[:]) != manifest.PolicyDexSHA256 {
		t.Fatal("fixture policy oracle changed")
	}
	run("push", dex, "/data/local/tmp/taild-map37-f0-policy.dex")
	f.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		f.seen[r.URL.Path]++
		f.mu.Unlock()
		w.WriteHeader(200)
	}))
	t.Cleanup(f.server.Close)
	return f
}

func (f *appAccessNativeFixture) uid(user int, name string) int {
	return f.uids[fmt.Sprintf("%d/io.github.darkaxt.taild.fixture.%s", user, name)]
}
func (f *appAccessNativeFixture) policy(args ...string) string {
	return f.run(append([]string{"shell", "env", "CLASSPATH=/data/local/tmp/taild-map37-f0-policy.dex", "app_process", "/system/bin", "io.github.darkaxt.taild.fixture.PolicyControl"}, args...)...)
}
func (f *appAccessNativeFixture) rule(chain, uid, rule int) {
	f.policy("rule", strconv.Itoa(chain), strconv.Itoa(uid), strconv.Itoa(rule))
}
func (f *appAccessNativeFixture) chain(chain int, enabled bool) {
	f.policy("chain", strconv.Itoa(chain), strconv.FormatBool(enabled))
}
func (f *appAccessNativeFixture) check(chain, uid int, enabled bool, rule int) {
	want := fmt.Sprintf("CHAIN=%d ENABLED=%t UID=%d RULE=%d", chain, enabled, uid, rule)
	if actual := strings.TrimSpace(f.policy("inspect", strconv.Itoa(chain), strconv.Itoa(uid))); actual != want {
		f.t.Fatalf("firewall oracle: %q, want %q", actual, want)
	}
}
func (f *appAccessNativeFixture) probe(user int, name string, success bool) {
	f.next++
	path := fmt.Sprintf("/app-access/probe-%d", f.next)
	target := strings.Replace(f.server.URL, "127.0.0.1", "10.0.2.2", 1) + path
	output := f.run("shell", "am", "broadcast", "--user", strconv.Itoa(user), "-f", "0x20", "-n", "io.github.darkaxt.taild.fixture."+name+"/io.github.darkaxt.taild.fixture.ProbeReceiver", "--es", "url", target)
	f.mu.Lock()
	hits := f.seen[path]
	f.mu.Unlock()
	if success {
		if !strings.Contains(output, `data="HTTP_200"`) || hits != 1 {
			f.t.Fatalf("fixture connectivity was not delivered: profile=%d app=%s hits=%d %s", user, name, hits, output)
		}
	} else {
		if !strings.Contains(output, `data="FAILED_`) || hits != 0 {
			f.t.Fatalf("blocked fixture unexpectedly delivered traffic: profile=%d app=%s hits=%d %s", user, name, hits, output)
		}
	}
	f.t.Logf("real app probe profile=%d app=%s success=%t server_receipts=%d", user, name, success, hits)
}
func (f *appAccessNativeFixture) pair(user int, success bool) {
	f.probe(user, "one", success)
	f.probe(user, "two", success)
}
func (f *appAccessNativeFixture) restartBackend() {
	info := f.run("shell", "dumpsys", "package", "moe.shizuku.privileged.api")
	match := regexp.MustCompile(`(?m)^\s*legacyNativeLibraryDir=(/data/app/[-A-Za-z0-9_~=./]+/lib)\s*$`).FindStringSubmatch(info)
	if len(match) != 2 || !strings.Contains(info, "primaryCpuAbi=x86_64") {
		f.t.Fatal("Shizuku installed native identity unavailable")
	}
	output := f.run("shell", match[1]+"/x86_64/libshizuku.so")
	if !strings.Contains(output, "shizuku_starter exit with 0") {
		f.t.Fatalf("Shizuku starter: %s", output)
	}
}
func (f *appAccessNativeFixture) phase(phase string) {
	own, other := f.uid(0, "one"), f.uid(0, "other")
	switch phase {
	case "app-access-ensure-backend":
		if !regexp.MustCompile(`(?m)^shizuku_server\s*$`).MatchString(f.run("shell", "ps", "-A", "-o", "ARGS")) {
			f.restartBackend()
		}
	case "app-access-before":
		actual := strings.TrimSpace(f.policy("inspect", "8", strconv.Itoa(own)))
		if actual != fmt.Sprintf("CHAIN=8 ENABLED=false UID=%d RULE=1", own) && actual != fmt.Sprintf("CHAIN=8 ENABLED=true UID=%d RULE=1", own) {
			f.t.Fatalf("Owned UID must be permitted before the roundtrip: %s", actual)
		}
		f.pair(0, true)
		f.probe(0, "other", true)
	case "app-access-blocked", "app-access-before-reboot", "app-access-pending-reconciled":
		f.check(8, own, true, 2)
		f.pair(0, false)
		f.probe(0, "other", true)
	case "app-access-stop-backend", "app-access-drop-response":
		pid := strings.TrimSpace(f.run("shell", "pidof", "shizuku_server"))
		if !regexp.MustCompile(`^\d+$`).MatchString(pid) {
			f.t.Fatal("one owned Shizuku server required")
		}
		info := f.run("shell", "ps", "-p", pid, "-o", "UID,ARGS")
		if !strings.Contains(info, "2000") || !strings.Contains(info, "shizuku_server") {
			f.t.Fatalf("unexpected server identity: %s", info)
		}
		f.run("shell", "kill", pid)
		f.check(8, own, true, 2)
		f.pair(0, false)
	case "app-access-restart-backend":
		f.restartBackend()
	case "app-access-unblocked", "app-access-final-restored":
		f.check(8, own, true, 1)
		f.pair(0, true)
	case "app-access-reboot-reconciled":
		f.check(8, own, false, 1)
		f.pair(0, true)
	case "app-access-profile-before":
		f.pair(*appAccessProfile, true)
		f.pair(0, true)
	case "app-access-profile-blocked", "app-access-profile-reconciled":
		f.check(8, f.uid(*appAccessProfile, "one"), true, 2)
		f.pair(*appAccessProfile, false)
		f.pair(0, true)
	case "app-access-profile-unblocked":
		f.check(8, f.uid(*appAccessProfile, "one"), true, 1)
		f.pair(*appAccessProfile, true)
	case "app-access-seed-external":
		f.rule(8, other, 2)
		f.rule(9, other, 2)
		f.chain(9, true)
	case "app-access-coexist-blocked":
		f.check(8, other, true, 2)
		f.check(9, other, true, 2)
		f.pair(0, false)
		f.probe(0, "other", false)
	case "app-access-coexist-unblocked":
		f.check(8, other, true, 2)
		f.check(9, other, true, 2)
		f.pair(0, true)
		f.probe(0, "other", false)
	case "app-access-seed-disabled-external":
		f.rule(9, other, 1)
		f.chain(9, false)
		f.chain(8, false)
	case "app-access-refused-foreign-activation":
		f.check(8, other, false, 2)
		f.check(8, own, false, 1)
		f.pair(0, true)
	case "app-access-clear-external":
		f.rule(8, other, 1)
	case "app-access-change-identity":
		f.run("install", "-r", f.twoAPK)
	case "app-access-stale-refused":
		f.check(8, own, false, 1)
		f.pair(0, true)
	case "app-access-after-reboot":
		f.check(8, own, false, 1)
		f.pair(0, true)
	}
}

func appAccessRequired(class string) []string {
	switch class {
	case "TailDAppAccessNativeTest":
		return []string{"app-access-before", "app-access-blocked", "app-access-stop-backend", "app-access-restart-backend", "assert-read-only-dashboard"}
	case "TailDAppAccessRestartNativeTest":
		return []string{"app-access-unblocked", "app-access-profile-blocked", "app-access-profile-unblocked", "app-access-coexist-unblocked", "app-access-refused-foreign-activation", "app-access-stale-refused", "app-access-before-reboot", "assert-read-only-dashboard"}
	case "TailDAppAccessFailureNativeTest":
		return []string{"app-access-before", "switch-theme", "capture-app-access-auto-dark", "app-access-drop-response", "capture-app-access-pending", "app-access-pending-reconciled", "app-access-final-restored", "app-access-profile-reconciled", "app-access-profile-unblocked", "assert-read-only-dashboard"}
	case "TailDAppAccessRebootNativeTest":
		return []string{"app-access-after-reboot", "app-access-reboot-reconciled", "app-access-final-restored", "assert-read-only-dashboard"}
	}
	return nil
}
