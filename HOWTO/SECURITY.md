# Security (cloud gate)

## Mutual TLS

The HTTPS listener (`run.py` / `swmcloudgate.start`) uses:

| File | Role |
|------|------|
| `$SPOOL/cluster/cert.pem` | Trust store for **client** certificates (`ssl_ca_certs`) |
| `$SPOOL/node/cert.pem` + `key.pem` | Gate **server** identity |

`$SPOOL` defaults to `/opt/swm/spool/secure`. Set `SWM_GATE_SPOOL` or `SWM_SPOOL`
(then `$SWM_SPOOL/secure`) to override.

Client certificates are **required** (`ssl.CERT_REQUIRED`). Sky Port
(`wm_gate`) presents the node certificate. Clients without a cert cannot
complete the handshake.

Any certificate signed by the cluster CA can satisfy the handshake. Prefer
keeping user private keys off hosts that can reach the gate port. Application
fingerprint helpers live in `swmcloudgate.tls.client_cert_allowed` for further
pinning when the ASGI stack exposes the peer certificate.

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
