#!/usr/bin/env bash
# SonarQube Community Build on the benchmark in the current directory.
#
# Follows BenchmarkJava/scripts/runSonarQube.sh: a throwaway SonarQube and the
# scanner, both in Docker, then the project's issues and hotspots written to
# results/ as the JSON that BenchmarkUtils' SonarQubeJsonReader reads. Two
# differences, each because the original does not work as written:
#   - Java is compiled first. The original points sonar.java.binaries at a
#     `target` that a fresh checkout does not have, so the Java analyser runs
#     without bytecode or libraries.
#   - The export is export.py, not BenchmarkJava's SonarReport, which asks for
#     hotspots with `projectKey=` - a parameter current SonarQube rejects.
# Mapping rules to CWEs and scoring stay with BenchmarkUtils.
#
# Needs: docker, curl, jq, python3; for Java also mvn.
# Given by the comparator: BENCHMARK_LANGUAGE, BENCHMARK_RESULTS_PREFIX, TOOL_DIR.

set -euo pipefail
: "${BENCHMARK_LANGUAGE:?}" "${BENCHMARK_RESULTS_PREFIX:?}" "${TOOL_DIR:?}"

# Pinned, so a rerun scores the same analyser.
server_image="sonarqube:26.10.0.133078-community"
scanner_image="sonarsource/sonar-scanner-cli@sha256:47956b669bf486bdad919e1cbd0533223515aa0b6d1d31763e5a3754942df6d7"

container="sonarqube-benchmark-$$"
port="9876"
host="http://localhost:$port"
project="benchmark"
user="admin"
password="P4ssword!!!!"

docker run --rm -d --name "$container" -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true \
  -p "127.0.0.1:$port:9000" "$server_image" > /dev/null
trap 'docker stop "$container" > /dev/null 2>&1 || true' EXIT

echo "Waiting for SonarQube to be up..."
for _ in $(seq 120); do
  [[ "$(curl -s "$host/api/system/status" | jq -r '.status' 2>/dev/null)" == "UP" ]] && break
  sleep 5
done
[[ "$(curl -s "$host/api/system/status" | jq -r '.status')" == "UP" ]] || {
  echo "SonarQube did not come up in 10 minutes" >&2
  exit 1
}

curl -sf -u "$user:admin" -X POST "$host/api/users/change_password" \
  --data-urlencode "login=$user" --data-urlencode "password=$password" \
  --data-urlencode "previousPassword=admin" > /dev/null
curl -sf -u "$user:$password" -X POST "$host/api/projects/create" \
  --data-urlencode "project=$project" --data-urlencode "name=$project" > /dev/null
token="$(curl -sf -u "$user:$password" -X POST "$host/api/user_tokens/generate" \
  --data-urlencode "name=benchmark-$$" | jq -r '.token')"

case "$BENCHMARK_LANGUAGE" in
  java)
    echo "Compiling..."
    mvn -B -q compile dependency:copy-dependencies -DoutputDirectory=target/dependency
    properties=(
      -Dsonar.sources=src
      -Dsonar.java.binaries=target/classes
      "-Dsonar.java.libraries=target/dependency/*.jar"
      "-Dsonar.exclusions=results/**,scorecard/**,scripts/**,tools/**,VMs/**,**/*.js"
    )
    ;;
  python)
    properties=(
      -Dsonar.sources=.
      "-Dsonar.inclusions=**/*.py"
      "-Dsonar.exclusions=results/**,scorecard/**,scripts/**,venv/**"
      -Dsonar.python.version=3
    )
    ;;
  *)
    echo "no SonarQube setup for $BENCHMARK_LANGUAGE" >&2
    exit 1
    ;;
esac

echo "Scanning..."
server_ip="$(docker inspect "$container" | jq -r '.[0].NetworkSettings.Networks.bridge.IPAddress')"
# As the invoking user, so nothing the scanner writes is left owned by root.
docker run --rm --user "$(id -u):$(id -g)" -e SONAR_USER_HOME=/benchmark/.sonar \
  -e SONAR_SCANNER_OPTS=-Xmx4g -v "$(pwd)":/benchmark -w /benchmark "$scanner_image" \
  -Dsonar.projectBaseDir=/benchmark \
  -Dsonar.projectKey="$project" \
  -Dsonar.host.url="http://$server_ip:9000" \
  -Dsonar.token="$token" \
  -Dsonar.scm.disabled=true \
  -Dsonar.working.directory=/benchmark/.scannerwork \
  "${properties[@]}"

echo "Waiting for the analysis..."
while true; do
  status="$(curl -s -u "$token:" "$host/api/ce/component?component=$project" | jq -r '.current.status // empty')"
  case "$status" in
    SUCCESS) break ;;
    FAILED | CANCELED)
      echo "SonarQube analysis $status" >&2
      exit 1
      ;;
  esac
  sleep 5
done

version="$(curl -sf -u "$token:" "$host/api/server/version")"
python3 "$TOOL_DIR/export.py" "$host" "$token" "$project" \
  "results/${BENCHMARK_RESULTS_PREFIX}sonarqube-v${version}.json"
