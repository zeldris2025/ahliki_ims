#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def load_env_local():
    """Read KEY=VALUE lines from .env.local (local runs only; never in Docker or Azure).
    Variables already set in the terminal win."""
    path = Path(__file__).resolve().parent / '.env.local'
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"\''))


def main():
    """Run administrative tasks."""
    load_env_local()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ahliki_ims.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
