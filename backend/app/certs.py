"""TLS CA bundle bootstrap.

Some corporate / inspected networks present a TLS chain that Python's bundled
certifi roots don't recognise ("unable to get local issuer certificate"). On
Windows we build a combined CA bundle (certifi + the Windows ROOT/CA trust
stores, which include the local inspection root the machine actually trusts) and
point requests **and** botocore at it via env vars. This keeps verification ON
using the machine's real trusted roots — no ``verify=False``.

Safe no-op on non-Windows or when the env vars are already set.
"""
from __future__ import annotations

import logging
import os
import ssl
import sys
import time
from pathlib import Path

import certifi

from .config import DATA_DIR

logger = logging.getLogger("mediadna.certs")
_BUNDLE = DATA_DIR / "ca_bundle.pem"
_MAX_AGE = 60 * 60 * 24  # rebuild daily


def _build_bundle() -> bool:
    blocks = [Path(certifi.where()).read_bytes()]
    added = 0
    for store in ("ROOT", "CA"):
        try:
            for cert, enc, _trust in ssl.enum_certificates(store):  # type: ignore[attr-defined]
                if enc == "x509_asn":
                    blocks.append(ssl.DER_cert_to_PEM_cert(cert).encode())
                    added += 1
        except Exception as exc:  # pragma: no cover
            logger.warning("could not read Windows cert store %s: %s", store, exc)
    _BUNDLE.write_bytes(b"\n".join(blocks))
    logger.info("built CA bundle with %d system certs -> %s", added, _BUNDLE)
    return True


def ensure_ca_bundle() -> None:
    if sys.platform != "win32":
        return
    if not hasattr(ssl, "enum_certificates"):
        return
    try:
        fresh = _BUNDLE.exists() and (time.time() - _BUNDLE.stat().st_mtime) < _MAX_AGE
        if not fresh:
            _build_bundle()
        path = str(_BUNDLE.resolve())
        # Point requests/urllib and botocore at the combined bundle.
        for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "AWS_CA_BUNDLE"):
            os.environ.setdefault(var, path)
    except Exception as exc:  # pragma: no cover
        logger.warning("CA bundle bootstrap failed: %s", exc)
