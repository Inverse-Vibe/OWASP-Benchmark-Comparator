#!/usr/bin/env bash
# Insider through BenchmarkJava's scripts/runInsider.sh, unchanged. That script
# expects `insider` on PATH; this downloads the latest release once into
# TOOL_CACHE and puts it there.

set -euo pipefail
: "${TOOL_CACHE:?}"

if [[ ! -x "$TOOL_CACHE/insider" ]]; then
  echo "Downloading Insider..."
  url=$(curl -sSf https://api.github.com/repos/insidersec/insider/releases/latest \
    | jq -r '.assets[].browser_download_url | select(test("linux_x86_64.tar.gz$"))')
  curl -sSfL "$url" | tar -xz -C "$TOOL_CACHE" insider
fi

PATH="$TOOL_CACHE:$PATH" bash scripts/runInsider.sh
