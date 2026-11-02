#!/usr/bin/env bash
# ShiftLeft Scan through BenchmarkJava's scripts/runShiftLeftScan.sh, unchanged.
#
# That script analyses the checkout as it finds it, and its class-file analyser
# needs the project built - on a fresh checkout it reports nothing at all. So the
# project is packaged first, as BenchmarkJava's own README builds it.
#
# Its container also runs as root and leaves what it writes owned by root, which
# nothing outside a container can clean up; afterwards the same image hands the
# checkout back to the invoking user.

mvn -B -q -DskipTests package || exit 1
bash scripts/runShiftLeftScan.sh
status=$?
docker run --rm -v "$PWD":/app --entrypoint chown docker.io/shiftleft/scan:latest \
  -R "$(id -u):$(id -g)" /app
exit $status
