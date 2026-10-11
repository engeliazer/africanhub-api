"""
Ensure Redis and Celery mail worker are running before bulk mail jobs.

Requires one-time server setup (systemd units + optional passwordless sudo).
See MAIL_WORKER_OPS.md.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAIL_QUEUE = "mail_processing"


def _app_root() -> Path:
    return Path(os.getenv("APP_ROOT", os.getcwd())).resolve()


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default).lower()).strip().lower() in ("1", "true", "yes")


def _executable(name: str, *fallback_paths: str) -> str:
    """Resolve CLI tools when Gunicorn's PATH is minimal (common on systemd)."""
    found = shutil.which(name)
    if found:
        return found
    for path in fallback_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return name


PGREP = lambda: _executable("pgrep", "/usr/bin/pgrep", "/bin/pgrep")
PKILL = lambda: _executable("pkill", "/usr/bin/pkill", "/bin/pkill")
SYSTEMCTL = lambda: _executable("systemctl", "/bin/systemctl", "/usr/bin/systemctl")
SUDO = lambda: _executable("sudo", "/usr/bin/sudo", "/bin/sudo")


def _mail_worker_systemd_unit() -> str:
    return os.getenv("MAIL_WORKER_SYSTEMD_UNIT", "africanhub-celery-mail.service").strip()


def _systemd_unit_is_active(unit: str) -> tuple[bool, str | None]:
    if not unit:
        return False, "systemd unit not configured"
    try:
        proc = subprocess.run(
            [SYSTEMCTL(), "is-active", unit],
            capture_output=True,
            text=True,
            timeout=10,
        )
        state = (proc.stdout or "").strip()
        if proc.returncode == 0 and state == "active":
            return True, None
        return False, state or "inactive"
    except Exception as exc:
        return False, str(exc)


def _redis_client():
    import redis

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD") or None
    if password:
        return redis.Redis(host=host, port=port, password=password, decode_responses=True)
    return redis.Redis(host=host, port=port, decode_responses=True)


def redis_is_up() -> tuple[bool, str | None]:
    try:
        if _redis_client().ping():
            return True, None
        return False, "Redis ping failed"
    except Exception as exc:
        return False, str(exc)


def mail_worker_is_running() -> tuple[bool, str | None]:
    unit = _mail_worker_systemd_unit()
    if unit:
        active, err = _systemd_unit_is_active(unit)
        if active:
            return True, None
        if err and err not in ("inactive", "failed", "deactivating"):
            logger.debug("systemd is-active %s: %s", unit, err)

    try:
        result = subprocess.run(
            [PGREP(), "-f", r"celery.*mail_processing"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, None
        if unit:
            return False, f"Unit {unit} not active"
        return False, "No Celery process for mail_processing queue"
    except Exception as exc:
        return False, str(exc)


def _run_systemctl(action: str, unit: str) -> tuple[bool, str]:
    unit = unit.strip()
    if not unit:
        return False, "systemd unit not configured"
    cmd = [SYSTEMCTL(), action, unit]
    if _env_bool("MAIL_WORKER_USE_SUDO", True):
        cmd = [SUDO(), "-n"] + cmd
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return True, (proc.stdout or proc.stderr or "").strip()
        return False, (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    except Exception as exc:
        return False, str(exc)


def _spawn_mail_worker() -> tuple[bool, str]:
    if not _env_bool("MAIL_WORKER_SPAWN_IF_MISSING", False):
        return False, "MAIL_WORKER_SPAWN_IF_MISSING is disabled"

    root = _app_root()
    celery_bin = root / "venv" / "bin" / "celery"
    if not celery_bin.is_file():
        return False, f"Celery binary not found at {celery_bin}"

    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "celery-mail-worker.log"

    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            subprocess.Popen(
                [
                    str(celery_bin),
                    "-A",
                    "celery_config.celery",
                    "worker",
                    "--loglevel=info",
                    "--concurrency=1",
                    f"--queues={MAIL_QUEUE}",
                ],
                cwd=str(root),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return True, f"Spawned mail worker (log: {log_path})"
    except Exception as exc:
        return False, str(exc)


def get_mail_worker_status() -> dict[str, Any]:
    redis_ok, redis_err = redis_is_up()
    worker_ok, worker_err = mail_worker_is_running()
    return {
        "redis_up": redis_ok,
        "redis_error": redis_err,
        "mail_worker_running": worker_ok,
        "mail_worker_error": worker_err,
        "ready": redis_ok and worker_ok,
        "mail_queue": MAIL_QUEUE,
    }


def ensure_mail_worker_ready() -> dict[str, Any]:
    """
    Try to start Redis and Celery mail worker when down.
    Controlled by MAIL_WORKER_AUTO_ENSURE (default true).
    """
    status = get_mail_worker_status()
    actions: list[str] = []

    if not _env_bool("MAIL_WORKER_AUTO_ENSURE", True):
        status["actions"] = actions
        status["auto_ensure_enabled"] = False
        return status

    status["auto_ensure_enabled"] = True

    if not status["redis_up"]:
        unit = os.getenv("REDIS_SYSTEMD_UNIT", "redis-server.service")
        ok, msg = _run_systemctl("start", unit)
        actions.append(f"systemctl start {unit}: {msg if ok else 'FAILED — ' + msg}")
        time.sleep(1)
        status["redis_up"], status["redis_error"] = redis_is_up()

    if not status["mail_worker_running"]:
        unit = os.getenv("MAIL_WORKER_SYSTEMD_UNIT", "africanhub-celery-mail.service")
        ok, msg = _run_systemctl("start", unit)
        if ok:
            actions.append(f"systemctl start {unit}: ok")
        else:
            actions.append(f"systemctl start {unit}: skipped/failed ({msg})")
            spawn_ok, spawn_msg = _spawn_mail_worker()
            actions.append(f"spawn worker: {spawn_msg}")
        time.sleep(3)
        status["mail_worker_running"], status["mail_worker_error"] = mail_worker_is_running()

    status["actions"] = actions
    status["ready"] = status["redis_up"] and status["mail_worker_running"]
    return status


def restart_mail_worker() -> dict[str, Any]:
    actions: list[str] = []
    unit = os.getenv("MAIL_WORKER_SYSTEMD_UNIT", "africanhub-celery-mail.service")

    ok, msg = _run_systemctl("restart", unit)
    if ok:
        actions.append(f"systemctl restart {unit}: ok")
    else:
        actions.append(f"systemctl restart {unit}: failed ({msg})")
        subprocess.run(
            [PKILL(), "-f", r"celery.*mail_processing"],
            capture_output=True,
        )
        time.sleep(2)
        spawn_ok, spawn_msg = _spawn_mail_worker()
        actions.append(f"spawn after pkill: {spawn_msg}")

    time.sleep(3)
    status = get_mail_worker_status()
    status["actions"] = actions
    return status
