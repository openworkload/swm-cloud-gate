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

## Related

- Sky Port trust model: [swm-core HOWTO/SECURITY.md](https://github.com/openworkload/swm-core/blob/master/HOWTO/SECURITY.md)
