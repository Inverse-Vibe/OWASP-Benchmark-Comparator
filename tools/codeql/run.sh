#!/usr/bin/env bash
# CodeQL through the benchmark's own scripts, unchanged: scripts/translateCodeQL.sh
# builds the database, scripts/runCodeQL.sh analyses it into the SARIF that
# BenchmarkUtils' CodeQLReader reads.
#
# Those scripts call CodeQL at a path relative to the benchmark checkout
# (BenchmarkJava: ../../tools/codeql-home/codeql, BenchmarkPython:
# ../tools/codeql-home/codeql), so the CodeQL bundle - downloaded once into
# TOOL_CACHE - is put there first.

set -euo pipefail
: "${BENCHMARK_LANGUAGE:?}" "${TOOL_CACHE:?}"

bundle="$TOOL_CACHE/codeql"
if [[ ! -x "$bundle/codeql" ]]; then
  echo "Downloading the CodeQL bundle..."
  curl -sSfL -o "$TOOL_CACHE/codeql-bundle.tar.gz" \
    https://github.com/github/codeql-action/releases/latest/download/codeql-bundle-linux64.tar.gz
  tar -xzf "$TOOL_CACHE/codeql-bundle.tar.gz" -C "$TOOL_CACHE"
  rm "$TOOL_CACHE/codeql-bundle.tar.gz"
fi
"$bundle/codeql" version | head -1

case "$BENCHMARK_LANGUAGE" in
  java) home="../../tools/codeql-home" ;;
  python) home="../tools/codeql-home" ;;
  *)
    echo "no CodeQL setup for $BENCHMARK_LANGUAGE" >&2
    exit 1
    ;;
esac
# A hard-linked copy, not a symlink: reached through a symlink by that relative
# path, CodeQL cannot find its own extractors ("no CodeQL extractor named
# 'python'"). Hard links cost no space.
mkdir -p "$home"
rm -rf "$home/codeql"
cp -al "$bundle" "$home/codeql"

bash scripts/translateCodeQL.sh
bash scripts/runCodeQL.sh
