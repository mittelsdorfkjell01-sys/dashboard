"""Pin a PostgreSQL URL to its IPv4 address without exposing credentials."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import socket
from typing import Callable

from sqlalchemy.engine import make_url


Resolver = Callable[..., list[tuple]]


def database_url_with_ipv4(
    database_url: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> tuple[str, str]:
    """Return the original hostname URL with a libpq ``hostaddr`` override."""

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")
    if not url.host:
        raise ValueError("DATABASE_URL must include a hostname")

    addresses = {
        str(ipaddress.IPv4Address(result[4][0]))
        for result in resolver(
            url.host,
            url.port or 5432,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    }
    if not addresses:
        raise ValueError(f"no IPv4 address found for database host {url.host}")
    address = sorted(addresses, key=ipaddress.IPv4Address)[0]
    rendered = url.update_query_dict({"hostaddr": address}).render_as_string(
        hide_password=False
    )
    return rendered, address


def write_github_environment(database_url: str, github_env: Path) -> str:
    resolved_url, address = database_url_with_ipv4(database_url)
    with github_env.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"DATABASE_URL={resolved_url}\n")
    return address


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--github-env",
        type=Path,
        default=os.getenv("GITHUB_ENV"),
        required=os.getenv("GITHUB_ENV") is None,
    )
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    try:
        address = write_github_environment(database_url, args.github_env)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"failed to resolve database IPv4 address: {exc}") from exc
    print(f"database IPv4 route configured: {address}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
