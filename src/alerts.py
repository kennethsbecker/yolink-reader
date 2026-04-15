#!/usr/bin/env python3
"""Battery alert system — cooldown check, alert recording, and email dispatch."""

import logging
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

import pymysql.connections

import src.config as config

logger = logging.getLogger(__name__)

# SMTP constants — rynok.org relay
_SMTP_HOST = "rynok.org"
_SMTP_PORT = 587
_SMTP_USER = "malachi@rynok.org"
_SMTP_PASSWORD = "jf5*6u2K7"
_FROM_ADDR = "malachi@rynok.org"
_TO_ADDR = "ken@rynok.org"

# Cooldown window
_COOLDOWN_HOURS = 24


def check_battery(
    conn: pymysql.connections.Connection,
    sensor_id: int,
    battery_level: Optional[int],
    threshold: int,
) -> bool:
    """Return True if a battery alert should fire for this sensor.

    Returns False if battery_level is None, above threshold, or an alert was
    already sent within the last 24 hours (cooldown active).

    Args:
        conn: Active PyMySQL connection.
        sensor_id: Primary key of the sensor row.
        battery_level: Current battery percentage reported by the sensor.
        threshold: Alert threshold from config.BATTERY_ALERT_THRESHOLD.
    """
    if battery_level is None or battery_level > threshold:
        return False

    cutoff: datetime = datetime.utcnow() - timedelta(hours=_COOLDOWN_HOURS)
    sql = """
        SELECT id FROM battery_alerts
        WHERE sensor_id = %s
          AND alerted_at >= %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (sensor_id, cutoff))
        row = cur.fetchone()

    if row:
        logger.debug(
            "Battery alert suppressed for sensor_id=%d — cooldown active", sensor_id
        )
        return False

    return True


def record_alert(
    conn: pymysql.connections.Connection,
    sensor_id: int,
    battery_level: int,
) -> None:
    """Insert a battery_alerts row for this sensor.

    Args:
        conn: Active PyMySQL connection.
        sensor_id: Primary key of the sensor row.
        battery_level: Battery percentage at time of alert.
    """
    sql = """
        INSERT INTO battery_alerts (sensor_id, battery_level)
        VALUES (%s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (sensor_id, battery_level))
    conn.commit()
    logger.debug("Battery alert recorded for sensor_id=%d", sensor_id)


def send_battery_alert(
    sensor_name: str,
    device_id: str,
    battery_level: int,
    location: Optional[str],
) -> None:
    """Send a low-battery alert email via rynok.org SMTP (STARTTLS, port 587).

    Args:
        sensor_name: Human-readable sensor name.
        device_id: YoLink device ID string.
        battery_level: Battery percentage to report.
        location: Sensor location label (may be None).
    """
    location_str: str = location if location else "Unknown"
    subject: str = f"YoLink Alert: Low Battery — {sensor_name}"
    body: str = (
        "Low battery detected.\n\n"
        f"Sensor: {sensor_name}\n"
        f"Location: {location_str}\n"
        f"Device ID: {device_id}\n"
        f"Battery level: {battery_level}%\n\n"
        "This alert will not repeat for 24 hours."
    )

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = _FROM_ADDR
    msg["To"] = _TO_ADDR

    context = ssl.create_default_context()
    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.login(_SMTP_USER, _SMTP_PASSWORD)
        smtp.sendmail(_FROM_ADDR, [_TO_ADDR], msg.as_string())

    logger.info(
        "Battery alert email sent — sensor=%s device=%s battery=%d%%",
        sensor_name, device_id, battery_level,
    )
