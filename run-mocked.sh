#!/bin/bash

PID_DIR=/tmp/cm-cloud-gate.tmp
mkdir -p $PID_DIR
PID_FILE=$PID_DIR/pid

source .venv/bin/activate
export SWM_TEST_CONFIG=test/data/responses.json
trap "rm -f $PID_FILE" EXIT
./start-cloud-gate.py &
echo $! > $PID_FILE
wait $!
