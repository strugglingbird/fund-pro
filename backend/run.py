"""Local entry point. Auto-loads backend/.env.local if present so the dev
workflow stays single-command. Production / Docker deployments keep using
environment variables supplied by the host or `docker compose --env-file`.
"""
import os
from pathlib import Path


def _load_local_env():
    env_path = Path(__file__).resolve().parent / ".env.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't override values already exported by the shell.
        os.environ.setdefault(key, value)


_load_local_env()

from app import run  # noqa: E402  (import after env loading)


if __name__ == "__main__":
    run()
