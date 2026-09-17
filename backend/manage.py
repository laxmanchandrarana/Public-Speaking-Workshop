#!/usr/bin/env python
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def main():
    # Load environment variables from .env located at repo root or backend/
    base_dir = Path(__file__).resolve().parent
    repo_root = base_dir.parent
    if (repo_root / ".env").exists():
        load_dotenv(repo_root / ".env")
    elif (base_dir / ".env").exists():
        load_dotenv(base_dir / ".env")

    # Add backend directory to sys.path so 'apps.x' and 'config' can be imported cleanly
    sys.path.insert(0, str(base_dir))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
