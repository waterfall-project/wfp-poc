"""JWT generator for local development.

Reads secrets from .env.development (or provided file) and prints a valid JWT.
"""

from __future__ import annotations

import argparse
import os
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
from dotenv import load_dotenv


def _load_env(env_file: Path) -> None:
    """Load environment variables from a file.

    Args:
        env_file: Path to the .env file to load.
    """
    if not env_file.exists():
        raise SystemExit(f"Env file not found: {env_file}")
    load_dotenv(env_file)


def _build_payload(
    user_id: str,
    company_id: str,
    email: str,
    expires_in: int,
) -> dict[str, Any]:
    """Build JWT payload with required claims.

    Args:
        user_id: User UUID string.
        company_id: Company UUID string.
        email: User email address.
        expires_in: Expiration duration in seconds.

    Returns:
        Payload dictionary for JWT encoding.
    """
    return {
        "user_id": user_id,
        "company_id": company_id,
        "email": email,
        "exp": int(time.time()) + expires_in,
    }


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for JWT generation.

    Returns:
        Parsed argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Generate a local JWT")
    parser.add_argument(
        "--env-file",
        default=".env.development",
        help="Path to environment file",
    )
    parser.add_argument("--user-id", help="User UUID (defaults to random)")
    parser.add_argument("--company-id", help="Company UUID (defaults to random)")
    parser.add_argument(
        "--email",
        default="user@example.com",
        help="Email claim value",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=3600,
        help="Token expiration in seconds",
    )
    return parser.parse_args()


def main() -> None:
    """Generate and print a JWT for local testing."""
    args = _parse_args()
    env_file = Path(args.env_file)
    _load_env(env_file)

    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise SystemExit("JWT_SECRET_KEY is required in the env file")

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    user_id = args.user_id or str(uuid.uuid4())
    company_id = args.company_id or str(uuid.uuid4())

    payload = _build_payload(user_id, company_id, args.email, args.expires_in)
    token = jwt.encode(payload, secret, algorithm=algorithm)
    print(token)


if __name__ == "__main__":
    main()
