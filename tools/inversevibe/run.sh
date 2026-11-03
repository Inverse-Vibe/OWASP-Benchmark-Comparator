#!/usr/bin/env bash
# InverseVibe on the OWASP Benchmark, through its protected binary.
#
# The binary (TOOL_DIR/inversevibe) embeds the engine encrypted; on each run it
# asks the licence service (INVERSEVIBE_URL) for the per-run key, decrypts the
# core into an anonymous memfd (never a file on disk), runs the static-review
# (SAST) analysis over this benchmark clone, and writes the SARIF that
# BenchmarkUtils' InverseVibeReader reads. The engine's own code never ships in
# the clear and never touches disk.
#
# The engine's dependency LIBRARIES (not the engine) are installed once into a
# venv under TOOL_CACHE from the shipped requirements. The shipped engine is
# -OO .pyc compiled for Python 3.12, so the interpreter that runs it MUST be
# 3.12 or the bytecode is rejected and the engine is "absent". Set
# INVERSEVIBE_PYTHON312 to a python3.12 if it is not on PATH, or set
# INVERSEVIBE_ENGINE_PYTHON directly to a 3.12 interpreter that already has the
# dependencies (then no venv is built). Nothing here names the benchmark: the
# binary hashes the tree it is given and the service decides whether it is pinned.

set -euo pipefail
: "${INVERSEVIBE_URL:?}" "${INVERSEVIBE_TOKEN:?}" "${BENCHMARK_LANGUAGE:?}"
: "${BENCHMARK_RESULTS_PREFIX:?}" "${TOOL_DIR:?}" "${TOOL_CACHE:?}"

if [[ -n "${INVERSEVIBE_ENGINE_PYTHON:-}" ]]; then
  engine_python="$INVERSEVIBE_ENGINE_PYTHON"
else
  py312="${INVERSEVIBE_PYTHON312:-python3.12}"
  if ! "$py312" -c 'import sys; assert sys.version_info[:2]==(3,12)' 2>/dev/null; then
    echo "InverseVibe needs Python 3.12 (the shipped engine is 3.12 bytecode)." >&2
    echo "Put python3.12 on PATH, or set INVERSEVIBE_PYTHON312=/path/to/python3.12." >&2
    exit 1
  fi
  venv="$TOOL_CACHE/deps-venv"
  if [[ ! -x "$venv/bin/python" ]]; then
    echo "Building the InverseVibe dependency venv (once, Python 3.12)..."
    "$py312" -m venv "$venv"
    "$venv/bin/pip" install -q --upgrade pip
    "$venv/bin/pip" install -q -r "$TOOL_DIR/requirements.txt"
  fi
  engine_python="$venv/bin/python"
fi

INVERSEVIBE_ENGINE_PYTHON="$engine_python" \
INVERSEVIBE_CODE_ROOT="$PWD" \
  "$TOOL_DIR/inversevibe"
