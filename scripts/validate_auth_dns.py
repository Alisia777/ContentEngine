#!/usr/bin/env python3
"""Fail-closed SPF, DKIM and DMARC validation for the Auth sending domain."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from collections.abc import Callable


DOMAIN_RE = re.compile(
    r"^(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)
SELECTOR_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$", re.I)
SPF_INCLUDE_RE = re.compile(
    r"^include:(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)
MAX_DNS_OUTPUT_BYTES = 64_000


class DnsValidationError(RuntimeError):
    """A safe DNS readiness failure."""


def _normalized_domain(value: str) -> str:
    return value.strip().lower().rstrip(".")


def parse_txt_output(output: str) -> list[str]:
    records: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            fragments = shlex.split(line, posix=True)
        except ValueError as exc:
            raise DnsValidationError("DNS TXT response is malformed") from exc
        if not fragments:
            continue
        records.append("".join(fragments).strip())
    return records


def parse_cname_output(output: str) -> list[str]:
    return [_normalized_domain(line) for line in output.splitlines() if line.strip()]


def dig(record_type: str, name: str) -> str:
    try:
        result = subprocess.run(
            ["dig", "+short", record_type, name],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DnsValidationError("Public DNS lookup failed") from exc
    if result.returncode != 0:
        raise DnsValidationError("Public DNS lookup failed")
    if len(result.stdout.encode("utf-8")) > MAX_DNS_OUTPUT_BYTES:
        raise DnsValidationError("Public DNS response is too large")
    return result.stdout


def validate_auth_dns(
    *,
    domain: str,
    selector: str,
    expected_spf_include: str,
    dkim_record_type: str,
    expected_dkim_value: str,
    lookup: Callable[[str, str], str] = dig,
) -> None:
    domain = _normalized_domain(domain)
    selector = selector.strip().lower()
    expected_spf_include = expected_spf_include.strip().lower()
    dkim_record_type = dkim_record_type.strip().upper()
    expected_dkim_value = expected_dkim_value.strip()

    if DOMAIN_RE.fullmatch(domain) is None:
        raise DnsValidationError("sending_domain has an invalid format")
    if SELECTOR_RE.fullmatch(selector) is None:
        raise DnsValidationError("dkim_selector has an invalid format")
    if SPF_INCLUDE_RE.fullmatch(expected_spf_include) is None:
        raise DnsValidationError(
            "expected_spf_include must be an exact include:provider.example token"
        )
    if dkim_record_type not in {"TXT", "CNAME"}:
        raise DnsValidationError("dkim_record_type must be TXT or CNAME")
    if not expected_dkim_value or any(
        ord(character) < 32 or ord(character) == 127
        for character in expected_dkim_value
    ):
        raise DnsValidationError("expected_dkim_value is required and must be safe")

    root_txt = parse_txt_output(lookup("TXT", domain))
    spf_records = [record for record in root_txt if record.lower().startswith("v=spf1")]
    if len(spf_records) != 1:
        raise DnsValidationError(
            "The sending domain must publish exactly one SPF record"
        )
    if expected_spf_include not in {token.lower() for token in spf_records[0].split()}:
        raise DnsValidationError("SPF does not authorize the reviewed mail provider")

    dmarc_txt = parse_txt_output(lookup("TXT", f"_dmarc.{domain}"))
    dmarc_records = [
        record for record in dmarc_txt if record.lower().startswith("v=dmarc1")
    ]
    if len(dmarc_records) != 1:
        raise DnsValidationError(
            "The sending domain must publish exactly one DMARC record"
        )
    if (
        re.search(
            r"(?:^|;)\s*p\s*=\s*(?:none|quarantine|reject)\s*(?:;|$)",
            dmarc_records[0],
            re.IGNORECASE,
        )
        is None
    ):
        raise DnsValidationError("DMARC must contain a valid p= policy")

    dkim_name = f"{selector}._domainkey.{domain}"
    dkim_txt = [
        record
        for record in parse_txt_output(lookup("TXT", dkim_name))
        if record.lower().startswith("v=dkim1")
    ]
    dkim_cname = parse_cname_output(lookup("CNAME", dkim_name))

    if dkim_record_type == "CNAME":
        expected_target = _normalized_domain(expected_dkim_value)
        if DOMAIN_RE.fullmatch(expected_target) is None:
            raise DnsValidationError("Expected DKIM CNAME target has an invalid format")
        if dkim_txt or len(dkim_cname) != 1 or dkim_cname[0] != expected_target:
            raise DnsValidationError(
                "DKIM CNAME does not exactly match the reviewed provider target"
            )
        return

    if dkim_cname or len(dkim_txt) != 1:
        raise DnsValidationError(
            "DKIM TXT does not exactly match the reviewed record type"
        )
    public_key = re.search(
        r"(?:^|;)\s*p\s*=\s*([^;\s]+)",
        dkim_txt[0],
        re.IGNORECASE,
    )
    if public_key is None:
        raise DnsValidationError("DKIM TXT contains an empty or revoked public key")
    if dkim_txt[0] != expected_dkim_value:
        raise DnsValidationError(
            "DKIM TXT does not exactly match the reviewed provider value"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate production Auth SPF, DKIM and DMARC records",
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--expected-spf-include", required=True)
    parser.add_argument("--dkim-record-type", choices=("TXT", "CNAME"), required=True)
    parser.add_argument("--expected-dkim-value", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_auth_dns(
            domain=args.domain,
            selector=args.selector,
            expected_spf_include=args.expected_spf_include,
            dkim_record_type=args.dkim_record_type,
            expected_dkim_value=args.expected_dkim_value,
        )
    except DnsValidationError as exc:
        print(f"Auth DNS validation failed: {exc}", file=sys.stderr)
        return 1
    print("SPF, DKIM and DMARC exactly match the reviewed provider records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
