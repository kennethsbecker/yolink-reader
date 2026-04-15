#!/usr/bin/env python3
"""Database access — PyMySQL connection and sensor/reading operations."""

from typing import Optional

import pymysql
import pymysql.cursors

import src.config as config


def get_connection() -> pymysql.connections.Connection:
    """Return a PyMySQL connection using config constants.

    Uses direct IP (216.177.141.16) — hostname resolution is unreliable.
    """
    return pymysql.connect(
        host=config.DB_HOST,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def upsert_sensor(
    conn: pymysql.connections.Connection,
    device_id: str,
    name: str,
    type_: str,
    location: Optional[str] = None,
) -> None:
    """Insert a sensor row, or update name/type/location if device_id already exists."""
    sql = """
        INSERT INTO sensors (device_id, name, type, location)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name     = VALUES(name),
            type     = VALUES(type),
            location = VALUES(location)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (device_id, name, type_, location))
    conn.commit()


def get_sensor_id(conn: pymysql.connections.Connection, device_id: str) -> Optional[int]:
    """Return sensors.id for a given device_id, or None if not found."""
    sql = "SELECT id FROM sensors WHERE device_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (device_id,))
        row = cur.fetchone()
    return row["id"] if row else None


def insert_reading(
    conn: pymysql.connections.Connection,
    sensor_id: int,
    temperature: Optional[float],
    humidity: Optional[float],
    battery: Optional[int],
    signal_strength: Optional[int],
) -> None:
    """Insert a sensor reading row."""
    sql = """
        INSERT INTO readings (sensor_id, temperature, humidity, battery, signal_strength)
        VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (sensor_id, temperature, humidity, battery, signal_strength))
    conn.commit()
