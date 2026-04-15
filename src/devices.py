#!/usr/bin/env python3
"""Device discovery — fetch devices from YoLink API and sync to DB."""

import json
import logging
import urllib.request
from typing import Any, Dict, List

import pymysql.connections

import src.config as config
from src.db import upsert_sensor

logger = logging.getLogger(__name__)


def fetch_devices(token: str) -> List[Dict[str, Any]]:
    """Call DeviceList.fetch via YoLink API and return a list of device dicts."""
    payload = json.dumps({
        "method": "DeviceList.fetch",
        "time": __import__("time").time_ns() // 1_000_000,
    }).encode()

    req = urllib.request.Request(
        config.YOLINK_API_URL,
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode())

    if body.get("code") != "000000":
        raise RuntimeError(f"YoLink API error: {body.get('code')} — {body.get('desc')}")

    devices: List[Dict[str, Any]] = body.get("data", {}).get("devices", [])
    logger.info("Fetched %d devices from YoLink", len(devices))
    return devices


def sync_sensors(
    conn: pymysql.connections.Connection,
    devices: List[Dict[str, Any]],
) -> None:
    """Upsert all devices into the sensors table.

    All device types are inserted; THSensor is the primary reading type
    but we track every device for completeness.
    """
    for device in devices:
        device_id: str = device.get("deviceId", "")
        name: str = device.get("name", device_id)
        type_: str = device.get("type", "Unknown")
        # YoLink does not return a location field — use None
        location = None

        if not device_id:
            logger.warning("Skipping device with no deviceId: %s", device)
            continue

        upsert_sensor(conn, device_id, name, type_, location)
        logger.debug("Upserted sensor: %s (%s) type=%s", name, device_id, type_)

    logger.info("Synced %d sensors to DB", len(devices))
