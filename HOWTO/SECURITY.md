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
