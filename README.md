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

Sky Port gate that provides cloud integration for [Open Workload](https://openworkload.org).
It is a FastAPI service used by [swm-core](https://github.com/openworkload/swm-core) to create,
query, and destroy cloud partitions (VMs) on **Azure** and **OpenStack**.

Source: [github.com/openworkload/swm-cloud-gate](https://github.com/openworkload/swm-cloud-gate)

# What it does

- Exposes HTTPS REST APIs for cloud partitions, flavors, and images
- Renders provider templates (ARM / Heat) and cloud-init for job VMs
- Talks to Azure (service principal + certificate) or OpenStack (libcloud)
- Runs with mutual TLS using Sky Port node/cluster certificates

Default listen address: `https://<fqdn>:8444`

# Requirements

* Python 3.12
* Sky Port TLS material under `/opt/swm/spool/secure/` (node + cluster certs)
* Provider credentials in `~/.swm/cloud-gate.yaml` (copy from `config/cloud-gate.yaml`)

For Azure setup (service principal, storage, registry), see [HOWTO/AZURE.md](HOWTO/AZURE.md).

# Setup

```bash
make prepare-venv
```

Copy and edit the config:

```bash
mkdir -p ~/.swm
cp config/cloud-gate.yaml ~/.swm/cloud-gate.yaml
# fill providers.azure (or openstack) credentials
```

# Run

Prefer the [swm-core](https://github.com/openworkload/swm-core) debug container so certs and Python deps match CI:

```bash
# from swm-core
make cr
# inside the container, in this repo:
./run.sh
```

Mocked mode (uses `test/data/responses.json`, no real cloud calls):

```bash
./run-mocked.sh
```

Optional: `SWM_GATE_WORKERS` controls uvicorn worker count (default `2` in `run.py`).

# Project layout

```text
swmcloudgate/
  main.py                 # FastAPI app + routers
  routers/azure/          # Azure connector, partitions, flavors, images, templates
  routers/openstack/      # OpenStack / Heat connector and templates
config/cloud-gate.yaml    # Config template
HOWTO/AZURE.md            # Azure account and credentials guide
test/                     # Unit tests
```

Cloud-init for Azure job VMs lives in:

* `swmcloudgate/routers/azure/templates/cloud-init.yaml`
* `swmcloudgate/routers/azure/templates/cloud-init.sh`

# Development

```bash
make format    # autoflake, isort, black
make check     # flake8, black --check, ruff, bandit
make test      # unittest
```

Run a single test module (example):

```bash
make azure_custom_data
# equivalent to: python -m unittest -v test/test_azure_custom_data.py
```

Regenerate pinned deps after editing `requirements.in`:

```bash
make requirements
```

Build / publish:

```bash
make package
make upload
```

# Contributing

Bug fixes can be submitted directly. For new features or larger changes, please open an issue first.

# License

BSD-3-Clause. Contributors retain copyright on their contributions.
