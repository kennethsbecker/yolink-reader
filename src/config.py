#!/usr/bin/env python3
"""Configuration — load all credentials from environment variables.

Caller is responsible for loading .env before importing this module.
"""

import os

# YoLink API
YOLINK_UAID: str = os.environ["YOLINK_UAID"]
YOLINK_SECRET: str = os.environ["YOLINK_SECRET"]
YOLINK_HOME_ID: str = os.environ["YOLINK_HOME_ID"]
YOLINK_TOKEN_URL: str = os.environ.get(
    "YOLINK_TOKEN_URL", "https://api.yosmart.com/open/yolink/token"
)
YOLINK_API_URL: str = os.environ.get(
    "YOLINK_API_URL", "https://api.yosmart.com/open/yolink/v2/api"
)
YOLINK_MQTT_HOST: str = os.environ.get("YOLINK_MQTT_HOST", "mqtt.api.yosmart.com")
YOLINK_MQTT_PORT: int = int(os.environ.get("YOLINK_MQTT_PORT", "8003"))

# MariaDB
DB_HOST: str = os.environ.get("DB_HOST", "216.177.141.16")
DB_NAME: str = os.environ["DB_NAME"]
DB_USER: str = os.environ["DB_USER"]
DB_PASSWORD: str = os.environ["DB_PASSWORD"]

# Application
BATTERY_ALERT_THRESHOLD: int = int(os.environ.get("BATTERY_ALERT_THRESHOLD", "20"))
LOG_PATH: str = os.environ.get("LOG_PATH", "logs/yolink.log")
