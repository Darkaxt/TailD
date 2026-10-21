#!/usr/bin/env bash
# Copyright (c) Tailscale Inc & AUTHORS
# SPDX-License-Identifier: BSD-3-Clause
set -euo pipefail

sample='VERSION_MAJOR=1
VERSION_MINOR=103
VERSION_PATCH=318
VERSION_SHORT="1.103.318"
VERSION_LONG="1.103.318-tabcdef-g123456789"
VERSION_GIT_HASH="abcdef"
VERSION_TRACK="unstable"
VERSION_XCODE="101.103.318"
VERSION_WINRES="1,103,318,0"'

expected='VERSION_MAJOR=1
VERSION_MINOR=103
VERSION_PATCH=312
VERSION_SHORT="1.103.312"
VERSION_LONG="1.103.312-tabcdef-g123456789"
VERSION_GIT_HASH="abcdef"
VERSION_TRACK="unstable"
VERSION_XCODE="101.103.312"
VERSION_WINRES="1,103,312,0"
TAILDNS_VERSION_NAME="1.103.312+3"'

actual="$(printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh 3 1.103.312)"
if [[ "$actual" != "$expected" ]]; then
  diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual")
  exit 1
fi

source /dev/stdin <<< "$actual"
if [[ ! "$VERSION_LONG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-t[0-9a-f]{6,}-g[0-9a-f]{6,}$ ]]; then
  echo "Go runtime version is malformed: $VERSION_LONG" >&2
  exit 1
fi

if ! grep -Fq 'versionName = getVersionProperty("TAILDNS_VERSION_NAME") ?: getVersionProperty("VERSION_LONG")' android/build.gradle.kts; then
  echo 'Android versionName does not prefer the TailDNS release name.' >&2
  exit 1
fi

standard_numeric_build='^v?[0-9]+\.[0-9]+\.[0-9]+\+[1-9][0-9]*$'
if [[ "1.103.312-taildns.6" =~ $standard_numeric_build ]]; then
  echo 'legacy TailDNS version unexpectedly matches the standard updater contract' >&2
  exit 1
fi
if [[ ! "1.103.312+7" =~ $standard_numeric_build || ! "v1.103.312+7" =~ $standard_numeric_build ]]; then
  echo 'corrected TailDNS version does not match the standard updater contract' >&2
  exit 1
fi

# ObtainX 2.10.00 falls back to a digit-shape comparison for non-standard
# versions. The leading v in a GitHub tag makes the legacy pair incompatible.
version_shape() {
  sed -E 's/[0-9]+/#/g' <<< "$1"
}
if [[ "$(version_shape '1.103.312-taildns.5')" == "$(version_shape 'v1.103.312-taildns.6')" ]]; then
  echo 'legacy installed and tag shapes unexpectedly reconcile' >&2
  exit 1
fi

current_sequence="${TAILDNS_VERSION_NAME##*+}"
next_version="${VERSION_SHORT}+$((current_sequence + 1))"
if [[ "$next_version" != "1.103.312+4" || ! "$next_version" =~ $standard_numeric_build ]]; then
  echo 'successive corrected TailDNS releases are not automatically comparable' >&2
  exit 1
fi

if ! grep -Fq 'test "$TAILDNS_VERSION_NAME" = "${VERSION_SHORT}+${release_sequence}"' .github/workflows/fork-release.yml; then
  echo 'Release workflow does not validate the TailDNS version name.' >&2
  exit 1
fi

if ! grep -Fq '[[ "$GITHUB_REF_NAME" =~ ^v[0-9]+\.[0-9]+\.[0-9]+\+[1-9][0-9]*$ ]]' .github/workflows/fork-release.yml; then
  echo 'Release workflow does not enforce the updater-compatible tag.' >&2
  exit 1
fi

if ! grep -Fq -- "- 'v*\\+*'" .github/workflows/fork-release.yml; then
  echo 'Release trigger does not escape the literal plus sign.' >&2
  exit 1
fi

if ! grep -Fq '[[ "$VERSION_LONG" =~ ^[0-9]+\.[0-9]+\.[0-9]+-t[0-9a-f]{6,}-g[0-9a-f]{6,}$ ]]' .github/workflows/fork-release.yml; then
  echo 'Release workflow does not reject a malformed Go runtime version.' >&2
  exit 1
fi

if ! grep -Fq 'windows_ldflags="$(bash version-ldflags.sh)"' .github/workflows/fork-release.yml; then
  echo 'Release workflow does not derive Windows linker stamps from the validated release version.' >&2
  exit 1
fi

package_step="$(sed -n '/- name: Package exact Windows client upgrade/,/- name: Preserve inert release inputs for isolated signing/p' .github/workflows/fork-release.yml)"
if ! grep -Fq 'go_cmd="$GITHUB_WORKSPACE/tool/go"' <<< "$package_step"; then
  echo 'Windows packaging does not invoke the repository Go wrapper directly.' >&2
  exit 1
fi

if grep -Fq 'go env GOROOT' <<< "$package_step"; then
  echo 'Windows packaging still depends on the unreliable wrapped GOROOT lookup.' >&2
  exit 1
fi

if [[ "$(grep -Fc '"$go_cmd" build' <<< "$package_step")" -ne 1 ]]; then
  echo 'Windows packaging does not build all executables in one Go invocation.' >&2
  exit 1
fi

if ! grep -Fq './cmd/taildns ./cmd/tailscaled ./cmd/tailscale' <<< "$package_step"; then
  echo 'The single Windows build does not include every required command.' >&2
  exit 1
fi

if ! grep -Fq 'mv release-input/windows/tailscaled.exe release-input/windows/taildnsd.exe' <<< "$package_step"; then
  echo 'Windows packaging does not rename the daemon to the TailDNS package name.' >&2
  exit 1
fi

if grep -Fq 'go version -m' <<< "$package_step"; then
  echo 'Windows packaging still relies on Go metadata that omits linker stamp values.' >&2
  exit 1
fi

if [[ "$(grep -Fc -- '-ldflags "$windows_ldflags"' <<< "$package_step")" -ne 1 ]]; then
  echo 'The single Windows build does not apply the validated linker stamps.' >&2
  exit 1
fi

if ! grep -Fq 'for expected in "$VERSION_LONG" "$VERSION_SHORT" "$VERSION_GIT_HASH" "$VERSION_EXTRA_HASH"' <<< "$package_step" ||
   ! grep -Fq 'grep -Fqa -- "$expected" "$GITHUB_WORKSPACE/release-input/windows/$binary"' <<< "$package_step"; then
  echo 'Release workflow does not verify every embedded Windows version stamp.' >&2
  exit 1
fi

if ! grep -Fq 'release_sequence:' .github/workflows/fork-build.yml ||
   ! grep -Fq 'echo "TAILDNS_RELEASE_SEQUENCE=$RELEASE_SEQUENCE" >> "$GITHUB_ENV"' .github/workflows/fork-build.yml; then
  echo 'Validation workflow cannot exercise release-version stamping.' >&2
  exit 1
fi

if printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh 0 1.103.312 >/dev/null 2>&1; then
  echo 'zero release sequence was accepted' >&2
  exit 1
fi

if printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh invalid 1.103.312 >/dev/null 2>&1; then
  echo 'non-numeric release sequence was accepted' >&2
  exit 1
fi

if printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh 3 invalid >/dev/null 2>&1; then
  echo 'non-numeric frozen upstream version was accepted' >&2
  exit 1
fi

echo 'TailDNS release version contract passed.'

# TailD uses a real fourth numeric component; the native runtime stays unchanged.
taild="$(printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh 36 1.103.312 .)"
source /dev/stdin <<< "$taild"
test "$TAILDNS_VERSION_NAME" = '1.103.312.36'
test "$VERSION_SHORT" = '1.103.312'
test "$VERSION_LONG" = '1.103.312-tabcdef-g123456789'
if printf '%s\n' "$sample" | bash scripts/append-taildns-version.sh 36 1.103.312 invalid >/dev/null 2>&1; then
  echo 'Invalid TailD release suffix separator was accepted' >&2
  exit 1
fi
echo 'TailD numeric release version contract passed.'
