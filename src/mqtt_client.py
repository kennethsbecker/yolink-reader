#!/usr/bin/env python3
"""MQTT client — subscribe to YoLink home topic and persist THSensor readings."""

import json
import logging
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt
import pymysql.connections

import src.config as config
from src.alerts import check_battery, record_alert, send_battery_alert
from src.db import get_connection, get_sensor_id, insert_reading

logger = logging.getLogger(__name__)

_token_provider: Optional[Callable[[], str]] = None
# Keyed by device_id; value is time.time() of last successful DB write.
_last_write: dict[str, float] = {}


def _get_sensor_meta(
    conn: pymysql.connections.Connection, sensor_id: int
) -> tuple[Optional[str], Optional[str]]:
    """Return (name, location) for the given sensor primary key."""
    sql = "SELECT name, location FROM sensors WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (sensor_id,))
        row = cur.fetchone()
    if row:
        return row["name"], row["location"]
    return None, None


def _on_connect(client: mqtt.Client, userdata: dict, flags: dict, rc: int) -> None:
    """Callback fired when the client connects (or reconnects) to the broker."""
    if rc == 0:
        topic = f"yl-home/{config.YOLINK_HOME_ID}/+/report"
        client.subscribe(topic)
        logger.info("MQTT connected — subscribed to %s", topic)
    else:
        logger.error("MQTT connect failed with code %d", rc)


def _on_disconnect(client: mqtt.Client, userdata: dict, rc: int) -> None:
    """Callback fired on disconnect; paho reconnect loop handles retry."""
    logger.warning("MQTT disconnected (rc=%d) — will reconnect", rc)


def _on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
    """Parse incoming MQTT message and persist THSensor readings to DB."""
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse MQTT payload: %s", exc)
        return

    event_type: str = payload.get("event", "")
    device_id: str = payload.get("deviceId", "")

    if not event_type.startswith("THSensor"):
        logger.debug("Ignored event type: %s (device %s)", event_type, device_id)
        return

    data: dict = payload.get("data", {})
    temperature: Optional[float] = data.get("temperature")
    humidity: Optional[float] = data.get("humidity")
    battery: Optional[int] = data.get("battery")

    lora_info: dict = data.get("loraInfo", {})
    signal_strength: Optional[int] = lora_info.get("signal")

    logger.info(
        "THSensor reading: device=%s temp=%s hum=%s bat=%s sig=%s",
        device_id, temperature, humidity, battery, signal_strength,
    )

    try:
        conn: pymysql.connections.Connection = get_connection()
        try:
            sensor_id = get_sensor_id(conn, device_id)
            if sensor_id is None:
                logger.warning("Unknown sensor %s — skipping reading", device_id)
                return

            # Hourly throttle — write at most one reading per sensor per hour.
            now: float = time.time()
            last: float = _last_write.get(device_id, 0.0)
            elapsed: float = now - last
            if elapsed < 3600:
                logger.debug(
                    "Throttled reading for %s — last write %.0fs ago", device_id, elapsed
                )
            else:
                insert_reading(conn, sensor_id, temperature, humidity, battery, signal_strength)
                _last_write[device_id] = now

            # Battery alert check — runs unconditionally regardless of throttle.
            if battery is not None and check_battery(
                conn, sensor_id, battery, config.BATTERY_ALERT_THRESHOLD
            ):
                sensor_name, location = _get_sensor_meta(conn, sensor_id)
                sensor_name = sensor_name or device_id
                try:
                    send_battery_alert(sensor_name, device_id, battery, location)
                    record_alert(conn, sensor_id, battery)
                    logger.info(
                        "Battery alert fired — sensor=%s device=%s battery=%d%%",
                        sensor_name, device_id, battery,
                    )
                except Exception as alert_exc:
                    logger.error(
                        "Battery alert failed for %s: %s", device_id, alert_exc
                    )
        finally:
            conn.close()
    except Exception as exc:
        logger.error("DB error persisting reading for %s: %s", device_id, exc)


def start_mqtt(token: str, token_provider: Optional[Callable[[], str]] = None) -> mqtt.Client:
    """Create, configure, and start the MQTT client loop in a background thread.

    Args:
        token: Current YoLink access token (used as MQTT password).
        token_provider: Optional callable that returns a fresh token on demand.
                        Not used in the initial connection but stored for future use.

    Returns:
        The running mqtt.Client instance.
    """
    global _token_provider
    _token_provider = token_provider

    client = mqtt.Client()
    client.username_pw_set(username=config.YOLINK_UAID, password=token)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    client.connect(config.YOLINK_MQTT_HOST, config.YOLINK_MQTT_PORT, keepalive=60)

    # loop_start() runs the network loop in a background daemon thread
    client.loop_start()
    logger.info(
        "MQTT loop started — broker=%s port=%d",
        config.YOLINK_MQTT_HOST,
        config.YOLINK_MQTT_PORT,
    )
    return client
