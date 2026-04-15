#!/usr/bin/env python3
"""YoLink Reader — entry point.

Loads .env, authenticates, syncs sensors, and starts the MQTT listener.
Token refresh runs in a background thread every 60 seconds.
"""

import logging
import os
import signal
import sys
import threading
import time
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


def _setup_logging(log_path: str) -> None:
    """Configure stdlib logging to file and stdout."""
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


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

    _setup_logging(config.LOG_PATH)
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

    # --- Token refresh thread ---
    stop_event = threading.Event()
    refresh_thread = threading.Thread(
        target=_token_refresh_loop,
        args=(stop_event,),
        daemon=True,
        name="token-refresh",
    )
    refresh_thread.start()

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
