# Defect Log — YoLink Reader

Format: each entry includes a defect ID, date found, description, status, and resolution.

Status values: `Open` | `Fixed` | `Deferred` | `Won't Fix`

---

## DEF-001 — Wrong YoLink API method for device list

**Date found:** 2026-04-14
**Status:** Fixed

**Description:**
`devices.py` called `DeviceList.fetch` which is not a valid YoLink API v2 method. The API returned error code `010203: method is not supported`, causing the app to crash on startup before MQTT connection was established.

**Resolution:**
Corrected method name to `Home.getDeviceList`. Committed in `fix: correct YoLink API method to Home.getDeviceList`.

---

## DEF-002 — MQTT credentials reversed

**Date found:** 2026-04-14
**Status:** Fixed

**Description:**
`mqtt_client.py` set the MQTT username to `YOLINK_UAID` and password to the access token. YoLink's MQTT broker expects the access token as the username and an empty string as the password. This caused MQTT connection to fail with error code 5 (Not Authorized) on every attempt.

**Resolution:**
Corrected `username_pw_set` call to use `username=token, password=""`. Committed in `fix: use access token as MQTT username with empty password`.

---

## DEF-003 — Remote MySQL connection blocked by hostname

**Date found:** 2026-04-14
**Status:** Fixed (workaround)

**Description:**
The hostname `mysql8.websitesource.net` is not reachable on port 3306 from the Raspberry Pi — connections time out. The websitesource.com shared hosting environment blocks remote MySQL connections via hostname. SSH access to the server is also not available.

**Resolution:**
Connecting via the server's direct IP address `216.177.141.16` bypasses the block. All database connections use the IP directly. `DB_HOST` in `.env` and `.env.example` is set to `216.177.141.16`.

**Note:** This is a workaround, not a root fix. If the server IP changes, the connection will break. Long-term fix would be to get the hostname allowlisted or migrate to a cloud database.

---
