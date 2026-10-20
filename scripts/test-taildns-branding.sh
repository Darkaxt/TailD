#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
strings_file="$repo_root/android/src/main/res/values/strings.xml"
fork_strings_file="$repo_root/android/src/main/res/values/local_dns.xml"
manifest_file="$repo_root/android/src/main/AndroidManifest.xml"
readme_file="$repo_root/README.md"

assert_contains() {
  local file="$1"
  local expected="$2"
  if ! grep -Fqx "$expected" "$file"; then
    printf 'Expected exact line in %s:\n%s\n' "$file" "$expected" >&2
    exit 1
  fi
}

assert_contains "$readme_file" '# TailD'
assert_contains "$fork_strings_file" '    <string name="fork_app_name" translatable="false">TailD</string>'
assert_contains "$strings_file" '    <string name="app_name" translatable="false">TailD</string>'
assert_contains "$strings_file" '    <string name="tile_name" translatable="false">TailD</string>'
assert_contains "$strings_file" '    <string name="about_view_header">About TailD</string>'
assert_contains "$strings_file" '    <string name="about_view_title">TailD for Android</string>'
assert_contains "$strings_file" '    <string name="about_tailscale">About TailD</string>'
assert_contains "$strings_file" '    <string name="welcome_to_tailscale">Welcome to TailD</string>'
assert_contains "$strings_file" '    <string name="welcome1">TailD is an independent client for securely connecting your devices through Tailscale.</string>'
assert_contains "$strings_file" '    <string name="managed_by_explainer">Your organization is managing TailD on this device. Some features might have been customized or hidden by your system administrator.</string>'
assert_contains "$strings_file" '    <string name="managed_by_explainer_orgName">%1$s is managing TailD on this device. Some features might have been customized or hidden by your system administrator.</string>'
assert_contains "$strings_file" '    <string name="prevents_the_user_from_disconnecting_tailscale">Prevents the user from disconnecting TailD.</string>'
assert_contains "$strings_file" '    <string name="forces_the_tailscale_client_to_always_use_the_exit_node_with_the_given_id">Forces the TailD client to always use the exit node with the given ID.</string>'
assert_contains "$strings_file" '    <string name="device_serial_number">Serial number of the device that is running TailD</string>'
assert_contains "$strings_file" '    <string name="device_serial_number_descr">Allows administrators to pass the serial number of the device to the TailD client using MDM.</string>'
assert_contains "$strings_file" '    <string name="permission_taildrop_dir">Give TailD access to a folder in order to be able to download incoming files sent to you via Taildrop.</string>'
assert_contains "$strings_file" '    <string name="title_connection_failed">TailD Connection Failed</string>'
assert_contains "$strings_file" '    <string name="body_open_tailscale">Tap here to open TailD.</string>'

if grep -Fq 'android:label="@string/app_name"' "$manifest_file"; then
  printf 'Manifest must use the fork-specific TailD label, not the upstream app_name label.\n' >&2
  exit 1
fi

assert_contains "$manifest_file" '        android:label="@string/fork_app_name"'

printf 'TailD product-branding contract passed.\n'
