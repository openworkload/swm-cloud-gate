#!/bin/bash

set -euo pipefail

PID_DIR=/tmp/cm-cloud-gate.tmp
mkdir -p "$PID_DIR"
PID_FILE=$PID_DIR/pid
GATE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$GATE_DIR"

source .venv/bin/activate
# Absolute paths: uvicorn workers may not keep the shell cwd for relative opens.
export SWM_TEST_CONFIG="${GATE_DIR}/test/data/responses.json"
export SWM_GATE_CONFIG="${SWM_GATE_CONFIG:-${GATE_DIR}/test/data/cloud-gate.yaml}"
# Bind loopback so GHA/CI clients do not depend on FQDN vs getfqdn() mismatches.
export SWM_GATE_HOST="${SWM_GATE_HOST:-127.0.0.1}"
# Single worker: simpler logs and avoids multi-process peercert patch races in CT.
export SWM_GATE_WORKERS="${SWM_GATE_WORKERS:-1}"
export PYTHONUNBUFFERED=1
# Skip uvicorn peercert injection in mocked CT; CERT_REQUIRED still enforces mTLS.
# Production (run.py without SWM_TEST_CONFIG) keeps fingerprint pin.
export SWM_GATE_DISABLE_PEER_CERT_PATCH="${SWM_GATE_DISABLE_PEER_CERT_PATCH:-1}"
trap 'rm -f "$PID_FILE"' EXIT
./run.py &
echo $! > "$PID_FILE"
wait $!
