#!/bin/bash

source .venv/bin/activate
export SWM_TEST_CONFIG=test/openstack.json
./run.py &
PID=$!
echo $PID > /var/tmp/swm-cloud-gate.pid
wait $PID
