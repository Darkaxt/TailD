#!/usr/bin/env bash
# Copyright (c) Tailscale Inc & AUTHORS
# SPDX-License-Identifier: BSD-3-Clause
set -euo pipefail

sequence="${1:-}"
base_version="${2:-}"
separator="${3:-+}"
if [[ "$separator" != '+' && "$separator" != '.' ]]; then
  echo 'Release suffix separator must be plus or dot.' >&2
  exit 1
fi
if [[ ! "$sequence" =~ ^[1-9][0-9]*$ ]]; then
  echo 'TailDNS release sequence must be a positive integer.' >&2
  exit 1
fi
if [[ ! "$base_version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo 'Frozen upstream version must contain three numeric components.' >&2
  exit 1
fi
base_major="${BASH_REMATCH[1]}"
base_minor="${BASH_REMATCH[2]}"
base_patch="${BASH_REMATCH[3]}"

mapfile -t lines
short=''
short_count=0
long_count=0
for line in "${lines[@]}"; do
  if [[ "$line" == VERSION_SHORT=\"*\" ]]; then
    short="${line#VERSION_SHORT=\"}"
    short="${short%\"}"
    short_count=$((short_count + 1))
  elif [[ "$line" == VERSION_LONG=* ]]; then
    long_count=$((long_count + 1))
  fi
done

if [[ "$short_count" -ne 1 || "$long_count" -ne 1 || ! "$short" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Upstream version metadata must contain one numeric VERSION_SHORT and one VERSION_LONG.' >&2
  exit 1
fi

for line in "${lines[@]}"; do
  case "$line" in
    VERSION_MAJOR=*) printf 'VERSION_MAJOR=%s\n' "$base_major" ;;
    VERSION_MINOR=*) printf 'VERSION_MINOR=%s\n' "$base_minor" ;;
    VERSION_PATCH=*) printf 'VERSION_PATCH=%s\n' "$base_patch" ;;
    VERSION_SHORT=*) printf 'VERSION_SHORT="%s"\n' "$base_version" ;;
    VERSION_LONG=*)
      long="${line#VERSION_LONG=\"}"
      long="${long%\"}"
      if [[ ! "$long" =~ ^[0-9]+\.[0-9]+\.[0-9]+(.*)$ ]]; then
        echo 'Upstream VERSION_LONG does not start with a numeric version.' >&2
        exit 1
      fi
      printf 'VERSION_LONG="%s%s"\n' "$base_version" "${BASH_REMATCH[1]}"
      ;;
    VERSION_XCODE=*) printf 'VERSION_XCODE="%s.%s.%s"\n' "$((base_major + 100))" "$base_minor" "$base_patch" ;;
    VERSION_WINRES=*) printf 'VERSION_WINRES="%s,%s,%s,0"\n' "$base_major" "$base_minor" "$base_patch" ;;
    *) printf '%s\n' "$line" ;;
  esac
done
printf 'TAILDNS_VERSION_NAME="%s%s%s"\n' "$base_version" "$separator" "$sequence"
