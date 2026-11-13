"""Generate a cryptographically secure JWT signing secret."""

from __future__ import annotations

import secrets


def generate_secret() -> str:
    return secrets.token_urlsafe(48)


if __name__ == "__main__":
    print(generate_secret())
