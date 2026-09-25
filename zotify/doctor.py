"""Local prerequisite checks that do not create a Spotify session."""
from __future__ import annotations

import json
import os
import stat
import shutil
from base64 import b64encode
from argparse import Namespace
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from zotify.config import Config
from zotify.const import CREDENTIALS_LOCATION, ROOT_PATH


def doctor(args: Namespace) -> int:
    checks: list[tuple[str, str | None]] = [
        ("ffmpeg", shutil.which("ffmpeg")),
        ("ffprobe", shutil.which("ffprobe")),
    ]

    config_location = getattr(args, "config_location", None)
    config_path = Path(config_location).expanduser() if config_location else Config._default_path()
    if config_path.suffix.lower() != ".json":
        config_path = config_path / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"MISSING: readable config file ({config_path}): {error}")
        return 1

    credential_location = (getattr(args, "credentials_location", None)
                           or config.get(CREDENTIALS_LOCATION, ""))
    if credential_location.startswith("."):
        root_value = getattr(args, "root_path", None) or config.get(ROOT_PATH, "~/Music/Zotify Music")
        credential_path = Path(root_value).expanduser() / Path(credential_location).relative_to(".")
    elif credential_location:
        credential_path = Path(credential_location).expanduser()
    else:
        credential_path = Config._default_path()
    if credential_path.suffix.lower() != ".json":
        credential_path = credential_path / "credentials.json"
    checks.append(("credentials.json", str(credential_path) if credential_path.is_file()
                   and credential_path.stat().st_size else None))

    if getattr(args, "doctor_session", False):
        session_status = None
        session_error_type = None
        if credential_path.is_file() and credential_path.stat().st_size:
            try:
                from librespot.core import Session
                credentials = json.loads(credential_path.read_text(encoding="utf-8"))
                builder = Session.Builder()
                builder.conf.store_credentials = False
                encoded = b64encode(json.dumps(credentials, ensure_ascii=True).encode("ascii"))
                session = builder.stored(encoded).create()
                session_status = "created successfully from saved credentials"
                try:
                    session.close()
                except Exception:
                    pass
            except Exception as error:
                # Error strings may contain provider details; keep diagnostics
                # useful without printing credentials or authentication tokens.
                session_error_type = type(error).__name__
        checks.append(("Spotify session", session_status))

    root_value = getattr(args, "root_path", None) or config.get(ROOT_PATH, "~/Music/Zotify Music")
    root_path = Path(root_value).expanduser()
    writable_path = root_path
    while not writable_path.exists() and writable_path != writable_path.parent:
        writable_path = writable_path.parent
    try:
        info = writable_path.stat()
        mode = info.st_mode
        groups = set(os.getgroups()) | {os.getegid()}
        if info.st_uid == os.geteuid():
            has_write_permission = bool(mode & stat.S_IWUSR)
        elif info.st_gid in groups:
            has_write_permission = bool(mode & stat.S_IWGRP)
        else:
            has_write_permission = bool(mode & stat.S_IWOTH)
    except OSError:
        has_write_permission = False
    checks.append((f"writable output directory ({root_path})",
                   str(writable_path) if has_write_permission else None))

    try:
        librespot = distribution("librespot")
        direct_url = json.loads(librespot.read_text("direct_url.json") or "{}")
        vcs = direct_url.get("vcs_info", {})
        commit = vcs.get("commit_id")
        source = direct_url.get("url", "")
        dependency = f"{librespot.version} from {source}@{commit}" if commit else None
    except (PackageNotFoundError, json.JSONDecodeError, OSError):
        dependency = None
    checks.append(("pinned librespot dependency", dependency))

    for name, value in checks:
        print(f"{'OK' if value else 'MISSING'}: {name}" + (f" — {value}" if value else ""))
    if getattr(args, "doctor_session", False) and session_error_type:
        print(f"DETAIL: Spotify session check failed ({session_error_type})")
    if not getattr(args, "doctor_session", False):
        print("Session login was not attempted; use --doctor-session to validate saved credentials online.")
    return 0 if all(value for _, value in checks) else 1
