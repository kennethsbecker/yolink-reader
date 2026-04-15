#!/usr/bin/env python3
"""YoLink Reader — entry point.

Loads .env, authenticates, syncs sensors, and starts the MQTT listener.
Token refresh and daily log rotation run in background threads.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path


def _load_env(env_path: str = ".env") -> None:
    """Read .env file and populate os.environ via setdefault (stdlib only)."""
    path = Path(env_path)
    if not path.exists():
        raise FileNotFoundError(f".env not found at {path.resolve()}")
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _log_filename(log_dir: Path) -> Path:
    """Return a dated log file path: logs/yolink_YYYY-MM-DD_HH-MM-SS.log"""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return log_dir / f"yolink_{stamp}.log"


def _setup_logging(log_path: str) -> logging.FileHandler:
    """Configure stdlib logging with a dated log file and stdout.

    Returns the FileHandler so it can be replaced during daily rotation.
    """
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = _log_filename(log_dir)
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Write header line at the top of every log file
    logging.info("=== YoLink Reader log started %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    return file_handler


def _purge_old_logs(log_dir: Path, max_age_days: int = 30) -> None:
    """Delete log files in log_dir older than max_age_days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for f in log_dir.glob("yolink_*.log"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            try:
                f.unlink()
                logging.info("Purged old log file: %s", f.name)
            except OSError as exc:
                logging.warning("Could not delete log file %s: %s", f.name, exc)


def _rotate_log(log_dir: Path, current_handler: logging.FileHandler) -> logging.FileHandler:
    """Close the current log file and open a new dated one. Returns the new handler."""
    root = logging.getLogger()

    # Remove and close old handler
    root.removeHandler(current_handler)
    current_handler.close()

    # Open new dated log file
    new_file = _log_filename(log_dir)
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    new_handler = logging.FileHandler(new_file)
    new_handler.setFormatter(fmt)
    root.addHandler(new_handler)

    # Write header line
    logging.info("=== YoLink Reader log started %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Purge logs older than 30 days
    _purge_old_logs(log_dir)

    return new_handler


def _log_rotation_loop(log_dir: Path, file_handler_ref: list, stop_event: threading.Event) -> None:
    """Background thread: rotate log at 00:01 every day."""
    while not stop_event.is_set():
        now = datetime.now()
        # Next 00:01
        next_rotation = now.replace(hour=0, minute=1, second=0, microsecond=0)
        if next_rotation <= now:
            next_rotation += timedelta(days=1)
        sleep_seconds = (next_rotation - datetime.now()).total_seconds()

        # Sleep in short chunks so we can respond to stop_event promptly
        while sleep_seconds > 0 and not stop_event.is_set():
            chunk = min(sleep_seconds, 30)
            time.sleep(chunk)
            sleep_seconds -= chunk

        if stop_event.is_set():
            break

        logging.info("Daily log rotation starting")
        new_handler = _rotate_log(log_dir, file_handler_ref[0])
        file_handler_ref[0] = new_handler
        logging.info("Log rotation complete — new file: %s", new_handler.baseFilename)


def _token_refresh_loop(stop_event: threading.Event) -> None:
    """Background thread: refresh YoLink token before expiry.

    Checks every 60 seconds; refreshes when fewer than 300 seconds remain.
    """
    import src.auth as auth  # imported after env is loaded

    logger = logging.getLogger(__name__)
    while not stop_event.is_set():
        time.sleep(60)
        if stop_event.is_set():
            break
        remaining = auth.token_expires_in()
        if remaining < 300:
            try:
                auth.get_token()
                logger.info("Token refreshed — expires in ~7200s")
            except Exception as exc:
                logger.error("Token refresh failed: %s", exc)


def main() -> None:
    """Bootstrap the YoLink reader service."""
    _load_env()

    # Import config after env is populated
    import src.config as config  # noqa: E402

    log_dir = Path(config.LOG_PATH).parent
    file_handler = _setup_logging(config.LOG_PATH)
    logger = logging.getLogger(__name__)
    logger.info("YoLink Reader starting up")

    import src.auth as auth
    from src.db import get_connection
    from src.devices import fetch_devices, sync_sensors
    from src.mqtt_client import start_mqtt

    # --- Authentication ---
    logger.info("Fetching YoLink access token")
    token = auth.get_token()
    logger.info("Token acquired — expires in %ds", int(auth.token_expires_in()))

    # --- DB connectivity & sensor sync ---
    logger.info("Connecting to MariaDB at %s", config.DB_HOST)
    conn = get_connection()
    try:
        logger.info("Fetching device list from YoLink API")
        devices = fetch_devices(token)
        sync_sensors(conn, devices)
    finally:
        conn.close()

    # --- Background threads ---
    stop_event = threading.Event()

    # Token refresh
    refresh_thread = threading.Thread(
        target=_token_refresh_loop,
        args=(stop_event,),
        daemon=True,
        name="token-refresh",
    )
    refresh_thread.start()

    # Daily log rotation — pass handler in a list so the thread can swap it
    file_handler_ref = [file_handler]
    rotation_thread = threading.Thread(
        target=_log_rotation_loop,
        args=(log_dir, file_handler_ref, stop_event),
        daemon=True,
        name="log-rotation",
    )
    rotation_thread.start()

    # --- MQTT ---
    mqtt_client = start_mqtt(token, token_provider=auth.get_token)

    # --- Graceful shutdown ---
    def _shutdown(signum: int, frame: object) -> None:
        logger.info("Shutdown signal received — stopping")
        stop_event.set()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("YoLink Reader running — press Ctrl+C to stop")
    signal.pause()


if __name__ == "__main__":
    main()
