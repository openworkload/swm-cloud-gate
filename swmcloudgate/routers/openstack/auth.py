"""Resolve OpenStack credentials without cross-request reuse."""

from __future__ import annotations

from typing import Tuple, Optional

from ... import config
from ...config import OpenStackProvider


class OpenStackAuthError(Exception):
    """Incomplete or invalid OpenStack credentials / auth settings."""


def load_openstack_provider() -> OpenStackProvider:
    try:
        return config.get_settings().providers.openstack
    except FileNotFoundError:
        return OpenStackProvider()


def resolve_openstack_credentials(
    username: Optional[str],
    password: Optional[str],
) -> Tuple[str, str]:
    """Return (username, password) for this request.

    Prefer a complete header pair. Otherwise use configured credentials.
    Never combine a partial header set with a prior session or with the
    other half of the config pair.
    """
    header_user = (username or "").strip()
    header_pass = (password or "").strip()

    if header_user and header_pass:
        return header_user, header_pass

    if header_user and not header_pass:
        # Username without password must not fall through to a sticky driver.
        # Config may still supply a full pair (Sky Port sends username only).
        pass
    elif header_pass and not header_user:
        raise OpenStackAuthError("OpenStack username and password are required together")

    cfg = load_openstack_provider()
    cfg_user = (cfg.username or "").strip()
    cfg_pass = (cfg.password or "").strip()
    if cfg_user and cfg_pass:
        return cfg_user, cfg_pass

    raise OpenStackAuthError("OpenStack username and password are required")
