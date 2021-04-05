#!/bin/bash

source .venv/bin/activate
export SWM_TEST_CONFIG=test/openstack.json
./run.py
