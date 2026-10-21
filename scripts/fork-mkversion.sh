#!/usr/bin/env bash
# Copyright (c) Tailscale Inc & AUTHORS
# SPDX-License-Identifier: BSD-3-Clause
set -euo pipefail

# Upstream mkversion reads require tailscale.com, not its replacement. Keep
# require/replace at the same pinned revision and supply this fork's git history.
versions=$(./tool/go list -m -f '{{.Version}} {{.Replace.Version}} {{.Replace.Path}}' tailscale.com)
read -r required replaced module <<< "$versions"
if [[ "$required" != "$replaced" || "$module" != "github.com/Darkaxt/tailscale" ]]; then
    echo 'Core requirement and fork replacement must pin the same revision.' >&2
    exit 1
fi
export TS_MKVERSION_OSS_GIT_CACHE="${TS_MKVERSION_OSS_GIT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/taildns-core}"
if [[ ! -e "$TS_MKVERSION_OSS_GIT_CACHE" ]]; then
    git clone --filter=blob:none https://github.com/Darkaxt/tailscale.git "$TS_MKVERSION_OSS_GIT_CACHE" >&2
fi
origin=$(git -C "$TS_MKVERSION_OSS_GIT_CACHE" remote get-url origin)
if [[ "$origin" != "https://github.com/Darkaxt/tailscale.git" ]]; then
    echo 'Version cache is not the TailDNS core fork; refusing to change it.' >&2
    exit 1
fi
if [[ -n "${TAILDNS_RELEASE_SEQUENCE:-}" ]]; then
    frozen_version="$(tr -d '\r\n' < TAILSCALE_BASE_VERSION.txt)"
    # TailD's fourth numeric component must participate in updater ordering.
    # The inherited TailDNS format remains the helper's default.
    separator='+'
    if [[ -f TAILD_ANDROID_SEQUENCE.txt ]]; then separator='.'; fi
    ./tool/go run tailscale.com/cmd/mkversion | bash scripts/append-taildns-version.sh "$TAILDNS_RELEASE_SEQUENCE" "$frozen_version" "$separator"
else
    exec ./tool/go run tailscale.com/cmd/mkversion
fi
