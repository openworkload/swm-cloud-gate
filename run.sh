#!/bin/bash

source .venv/bin/activate
./run.py &
PID=$!
echo $PID > /var/tmp/swm-cloud-gate.pid
wait $PID
