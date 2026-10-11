#!/bin/bash

PID_DIR=/tmp/cm-cloud-gate.tmp
mkdir -p $PID_DIR
PID_FILE=$PID_DIR/pid

source .venv/bin/activate
# Mocked HTTP payloads + OpenStack creds (wm_gate CT does not send password headers).
export SWM_TEST_CONFIG=test/data/responses.json
export SWM_GATE_CONFIG="${SWM_GATE_CONFIG:-test/data/cloud-gate.yaml}"
# Bind loopback so GHA/CI clients do not depend on FQDN vs getfqdn() mismatches.
export SWM_GATE_HOST="${SWM_GATE_HOST:-127.0.0.1}"
# Single worker: simpler logs and avoids multi-process peercert patch races in CT.
export SWM_GATE_WORKERS="${SWM_GATE_WORKERS:-1}"
trap "rm -f $PID_FILE" EXIT
./run.py &
echo $! > $PID_FILE
wait $!
