# YoLink Reader

Reads temperature, humidity, and battery data from YoLink sensors and stores readings to a MariaDB database on rynok.org. Sends email alerts when a sensor battery drops below the configured threshold.

---

## What it does

1. **Authenticates** with the YoLink API using OAuth2 (UAID + Secret Key)
2. **Syncs your device list** — all YoLink devices in your home are written to the `sensors` table on startup
3. **Connects to YoLink's MQTT broker** and subscribes to all sensor reports in real time
4. **Stores readings** — for each THSensor (temperature/humidity) report, writes one row to the `readings` table — at most once per hour per sensor
5. **Sends battery alerts** — if a sensor's battery drops to or below the threshold (default 20%), sends an email to `ken@rynok.org` via rynok.org SMTP. Will not repeat the alert for the same sensor within 24 hours.
6. **Refreshes the access token** automatically before it expires (token valid for 2 hours; refresh check runs every 60 seconds)

---

## Running the app

```bash
cd /home/ken/projects/yolink-reader
python3 -m src.main
```

The app runs in the foreground and logs to both the terminal and `logs/yolink.log`. Press Ctrl+C to stop cleanly.

---

## Configuration

Copy `.env.example` to `.env` and fill in the values:

```
YOLINK_UAID=ua_...
YOLINK_SECRET=sec_v1_...
YOLINK_HOME_ID=...
YOLINK_TOKEN_URL=https://api.yosmart.com/open/yolink/token
YOLINK_API_URL=https://api.yosmart.com/open/yolink/v2/api
YOLINK_MQTT_HOST=mqtt.api.yosmart.com
YOLINK_MQTT_PORT=8003
DB_HOST=216.177.141.16
DB_NAME=yolink
DB_USER=yolink_author
DB_PASSWORD=...
BATTERY_ALERT_THRESHOLD=20
LOG_PATH=logs/yolink.log
```

YoLink credentials are found in the YoLink mobile app under **Account → Advanced → User Access Credentials**.

---

## Database

MariaDB on `mysql8.websitesource.net` (connect via direct IP `216.177.141.16`). Database: `yolink`.

| Table | Purpose |
|-------|---------|
| `sensors` | One row per YoLink device. Populated on startup. |
| `readings` | One row per sensor per hour — temperature, humidity, battery, signal strength. |
| `battery_alerts` | One row per alert sent — used to enforce the 24-hour cooldown. |

Schema: `data/schema.sql`

---

## Project structure

```
yolink-reader/
├── src/
│   ├── main.py          — entry point; bootstraps auth, DB, MQTT
│   ├── config.py        — loads all settings from .env
│   ├── auth.py          — YoLink OAuth2 token fetch and refresh
│   ├── db.py            — MariaDB connection and query helpers
│   ├── devices.py       — fetches device list from YoLink API, syncs to DB
│   ├── mqtt_client.py   — MQTT subscriber; parses and stores readings
│   └── alerts.py        — battery threshold check, cooldown logic, email send
├── data/
│   └── schema.sql       — MariaDB schema
├── logs/
│   └── yolink.log       — runtime log (created on first run)
├── .env                 — credentials (not committed)
├── .env.example         — template
├── requirements.txt     — pymysql, paho-mqtt
└── DEFECTS.md           — known issues and defect log
```

---

## Dependencies

```
pymysql
paho-mqtt
```

Install: `pip3 install pymysql paho-mqtt`

---

## Known issues

See `DEFECTS.md`.
