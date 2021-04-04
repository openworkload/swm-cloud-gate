# swm-cloud-gate

SkyPort gate that provides cloud integration.
Part of Sky Workload Manager.

# Requirements
  * python >= 3.7

# Setup and development commands
  * make prepare-venv
  * make check
  * make format

# Run the gate
  * Run swm dev container (make cr)
  * source .venv/bin/activate
  * ./run.py

# Run the gate in test mode
  * Run swm dev container (make cr)
  * ./run-mocked.py

# References:
  * https://libcloud.readthedocs.io/en/stable/compute/examples.html
  * https://docs.openstack.org/api-ref/orchestration/v1/index.html
  * https://docs.python.org/3.3/library/http.client.html

