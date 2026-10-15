# Security (cloud gate)

## Mutual TLS

The HTTPS listener (`run.py` / `swmcloudgate.start`) uses:

| File | Role |
|------|------|
| `$SPOOL/cluster/ca-chain-cert.pem` (preferred) or `cert.pem` | Trust store for **client** certificates (`ssl_ca_certs`) |
| `$SPOOL/node/cert.pem` + `key.pem` | Gate **server** identity |

Use the CA chain when the cluster certificate is an intermediate under a grid
root. OpenSSL fails client verification with only the intermediate
(`unable to get issuer certificate`) and closes the TLS session.

`$SPOOL` defaults to `/opt/swm/spool/secure`. Set `SWM_GATE_SPOOL` or `SWM_SPOOL`
(then `$SWM_SPOOL/secure`) to override.

Client certificates are **required** (`ssl.CERT_REQUIRED`). Sky Port
(`wm_gate`) presents the node certificate. Clients without a cert cannot
complete the handshake.

When the ASGI scope exposes the peer certificate (uvicorn peercert patch),
middleware pins the fingerprint to `$SPOOL/node/cert.pem` (override with
`SWM_GATE_ALLOWED_CLIENT_CERT`). A mismatch returns HTTP 403. If peercert is
not in the scope (for example TestClient), the pin is skipped; handshake
`CERT_REQUIRED` still applies for HTTPS.

Do **not** send node private keys in HTTP bodies. Sky Port authenticates with
mTLS only.

## Error responses

The gate runs with FastAPI `debug=False`. Unexpected errors return HTTP 500 with
a generic `detail` body. Stack traces stay in server logs only and are not sent
to clients. Intentional validation failures (for example bad ports) still return
HTTP 400 with a short message and no traceback.

## Azure service principal certificate

Azure `CertificateCredential` uses gate-local PEM material:

1. `providers.azure.api_credentials.certificate_path` when set in
   `cloud-gate.yaml`, or
2. `$SPOOL/node/key.pem` + `$SPOOL/node/cert.pem` by default.

Request bodies must not carry private keys.

## Azure registry and storage secrets

Partition ARM deployments pass the container registry password and storage
account key as `securestring` parameters. Cloud-init scripts hold placeholders
only; ARM `replace` injects `base64(parameters(...))` into VM `customData`.

On the VM, cloud-init writes the bootstrap script to
`/var/lib/swm/bootstrap/swm-init.sh` with mode `0700`. The script removes
itself on `EXIT` so registry and storage secrets do not remain on filesystem.

Shared registry credentials (`user` / `password`) are used only when the job
image registry host matches `providers.azure.container_registry.server`.
Foreign registry hosts are rejected at partition create (HTTP 400). Short-lived
or per-registry pull tokens remain a follow-up.

## Azure NSG ports and SSH

Partition NSG rules do not open SSH from `*` by default. Set
`providers.azure.nsg_source_address_prefixes` to Sky Port egress CIDR(s), or set
`allow_ssh_from_internet: true` only for lab use.

Job-port rules from the `ports` header use the same CIDR list when it is set;
otherwise they use `*` (operators should set the list in production). The gate
validates port values (integers 1..65535), enforces `max_ingress_ports`, and
applies `allowed_ports` when that list is non-empty. Invalid ports return HTTP
400.

This NSG control is separate from swm-core `submission_address_allowlist`, which
limits TCP proxy upstream targets on the Sky Port side.

## Azure partition DELETE scope

Partition DELETE accepts only resource group names that start with `swm-` and
end with `-resource-group` (the create naming scheme). Other names return HTTP
400 and Azure delete is not called. Narrow the service principal scope in Azure
as well; see [AZURE.md](AZURE.md).

## OpenStack credentials and TLS

Set `providers.openstack` in `~/.swm/cloud-gate.yaml`:

| Field | Role |
|-------|------|
| `auth_url` | Keystone URL. Use `https://` in production. |
| `username` / `password` | Gate service account (used when request headers omit a full pair) |
| `project_name` / `domain_name` | OpenStack project and domain |
| `verify_ssl` | Default `true`. Do not disable in production. |
| `ca_cert` | Optional CA file path for libcloud |
| `allow_insecure_http` | Default `false`. Set `true` only for lab HTTP Keystone. |

Credential rules:

1. If both `username` and `password` headers are set, the gate uses that pair for the request.
2. Otherwise the gate uses `providers.openstack` username and password.
3. A blank or missing password does **not** reuse a prior libcloud session. The driver is cleared and the API returns HTTP 401 when no complete credentials exist.
4. Each request builds a fresh connector. Sessions are not shared across callers.

Sky Port (`wm_gate`) may send only `username`. Configure the OpenStack password in the gate yaml so those calls succeed.

## Related

- Sky Port trust model: [swm-core HOWTO/SECURITY.md](https://github.com/openworkload/swm-core/blob/master/HOWTO/SECURITY.md)
- OpenStack setup notes: [OPENSTACK.md](OPENSTACK.md)
