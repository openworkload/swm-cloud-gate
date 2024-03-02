<p align="center">
    <a href="https://github.com/openworkload/swm-cloud-gate/blob/master/LICENSE" alt="License">
        <img src="https://img.shields.io/github/license/openworkload/swm-cloud-gate" />
    </a>
    <a href="https://github.com/openworkload/swm-cloud-gate/actions/workflows/ci.yml" alt="Latest CI tests result">
        <img src="https://github.com/openworkload/swm-cloud-gate/actions/workflows/ci.yml/badge.svg?event=push" />
    </a>
</p>


Sky Port cloud gate
===================

This is a repository for Sky Port gate that provides cloud integration.
It is a part of the [Open Workload](https://openworkload.org) project.

# Requirements:
  * Python >= 3.10

# Preparations:
  * make prepare-venv
  * make format
  * make check

# Run the gate in foreground:
  * Run swm-core dev container (make cr)
  * ./run.sh

# Run the gate in foreground in a test mode:
  * Run swm-core dev container (make cr)
  * ./run-mocked.py
