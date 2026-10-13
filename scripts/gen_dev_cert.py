"""Development TLS certificate (Sprint 19: internet prototype, local loop).

Generates a self-signed cert for ``localhost``/``127.0.0.1`` so the TLS path
(https + wss) can be proven without exposing anything. NOT for production:
real deployments terminate TLS with a proper CA (Sprint 19 uses a private
network/VPN or hosted coordinator with real certs instead).

Prefers the ``openssl`` CLI, falls back to the ``cryptography`` package,
else prints PowerShell instructions.

Usage:
    python scripts/gen_dev_cert.py --out dev-tls [--host 127.0.0.1] [--days 30]

Writes ``<out>.pem`` (cert) and ``<out>.key`` (private key). The worker trusts
the cert via ``--ca-bundle <out>.pem``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a dev self-signed TLS cert")
    p.add_argument("--out", default="dev-tls", help="Output stem (writes <out>.pem + <out>.key)")
    p.add_argument("--host", default="127.0.0.1", help="CN / SAN IP or DNS name")
    p.add_argument("--days", type=int, default=30, help="Validity days")
    return p.parse_args(argv)


def _san(host: str) -> str:
    try:
        import ipaddress

        ipaddress.ip_address(host)
        return f"IP:{host}"
    except ValueError:
        return f"DNS:{host}"


def gen_with_openssl(cert: Path, key: Path, host: str, days: int) -> bool:
    if shutil.which("openssl") is None:
        return False
    san = _san(host)
    ext = f"subjectAltName={san},DNS:localhost,IP:127.0.0.1"
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(key), "-out", str(cert), "-days", str(days),
        "-subj", f"/CN={host}", "-addext", ext,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"openssl failed: {r.stderr.strip()}", flush=True)
        return False
    return True


def gen_with_cryptography(cert: Path, key: Path, host: str, days: int) -> bool:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        return False
    import datetime
    import ipaddress

    try:
        san_entry: x509.GeneralName = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        san_entry = x509.DNSName(host)
    key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert_obj = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key_obj.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(
            [san_entry, x509.DNSName("localhost"),
             x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key_obj, hashes.SHA256())
    )
    key.write_bytes(key_obj.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cert = Path(f"{args.out}.pem")
    key = Path(f"{args.out}.key")
    if cert.exists() or key.exists():
        print(f"refusing to overwrite existing {cert} / {key}; delete first", flush=True)
        return 1
    if gen_with_openssl(cert, key, args.host, args.days):
        print(f"wrote {cert} + {key} (openssl)", flush=True)
        return 0
    if gen_with_cryptography(cert, key, args.host, args.days):
        print(f"wrote {cert} + {key} (cryptography)", flush=True)
        return 0
    print(
        "neither openssl nor the cryptography package is available.\n"
        "On Windows PowerShell you can instead run:\n"
        '  $c = New-SelfSignedCertificate -DnsName "localhost","127.0.0.1" '
        "-CertStoreLocation Cert:\\CurrentUser\\My\n"
        "and export it, then point the worker at it with --ca-bundle.",
        flush=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
