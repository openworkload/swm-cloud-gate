# swm-cloud-gate

Sky Port gate that provides cloud integration.
Part of [Open Workload](http://openworkload.org) project.

# Requirements
  * python >= 3.9

# Setup and development commands
  * make prepare-venv
  * make check
  * make format

# Run the gate
  * Run swm-core dev container (make cr)
  * ./run.sh

# Run the gate in test mode
  * Run swm-core dev container (make cr)
  * ./run-mocked.py
