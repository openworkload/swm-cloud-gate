# OpenStack provider setup

Configure the OpenStack connector in `~/.swm/cloud-gate.yaml`.

## Required settings

Copy the template from `config/cloud-gate.yaml` and set:

```yaml
providers:
  openstack:
    auth_url: "https://keystone.example:5000"
    username: "swm-gate"
    password: "<secret>"
    project_name: "demo"
    domain_name: "Default"
    verify_ssl: true
    ca_cert: ""
    allow_insecure_http: false
```

1. Set `auth_url` to your Keystone endpoint. Use HTTPS.
2. Set `username` and `password` for the gate service account.
3. Set `project_name` and `domain_name` for that account.
4. Keep `verify_ssl: true` unless you use a private lab with a custom CA.
5. If Keystone uses a private CA, set `ca_cert` to the CA file path.

## Request headers

API scripts may send:

* `username`
* `password`

If both headers are non-empty, the gate uses them for that request only.
If the password header is missing, the gate uses the yaml credentials.
The gate never keeps the previous caller's libcloud session when the password is blank.

## TLS

The gate enables libcloud certificate verification when `verify_ssl` is true.
HTTP Keystone URLs are rejected unless `allow_insecure_http` is true.

## Related

* [SECURITY.md](SECURITY.md) -- credential reuse rules and mTLS
* [README.md](../README.md) -- run and test the gate
