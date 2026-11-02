#!/usr/bin/env bash
# ShiftLeft Scan through BenchmarkJava's scripts/runShiftLeftScan.sh, unchanged.
# Its container builds the project as root, leaving target/ and the rest owned by
# root - which nothing outside a container can then clean up - so afterwards the
# same image hands everything under the checkout back to the invoking user.

bash scripts/runShiftLeftScan.sh
status=$?
docker run --rm -v "$PWD":/app --entrypoint chown docker.io/shiftleft/scan:latest \
  -R "$(id -u):$(id -g)" /app
exit $status
