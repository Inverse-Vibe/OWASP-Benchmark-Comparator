#!/usr/bin/env bash
# Bearer through the benchmark's own scripts/runBearer.sh, unchanged. The Bearer
# image runs as its own user, which cannot write into a results/ owned by the
# user running the benchmark, so results/ is opened to it first.

set -euo pipefail

chmod a+w results
bash scripts/runBearer.sh
