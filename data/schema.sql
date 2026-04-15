-- yolink-reader MariaDB schema
-- Deploy: mysql -h <host> -u <user> -p <db> < schema.sql

CREATE TABLE IF NOT EXISTS sensors (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    device_id  VARCHAR(64)  NOT NULL UNIQUE,
    name       VARCHAR(128) NOT NULL,
    type       VARCHAR(64)  NOT NULL,
    location   VARCHAR(128),
    status     VARCHAR(32)  DEFAULT 'active',
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS readings (
    id              INT          AUTO_INCREMENT PRIMARY KEY,
    sensor_id       INT          NOT NULL,
    temperature     DECIMAL(5,2),
    humidity        DECIMAL(5,2),
    pressure        DECIMAL(7,2) NULL,
    battery         INT,
    signal_strength INT,
    recorded_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_readings_sensor FOREIGN KEY (sensor_id) REFERENCES sensors(id),
    INDEX idx_readings_sensor_id  (sensor_id),
    INDEX idx_readings_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS battery_alerts (
    id            INT      AUTO_INCREMENT PRIMARY KEY,
    sensor_id     INT      NOT NULL,
    battery_level INT      NOT NULL,
    alerted_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_battery_alerts_sensor FOREIGN KEY (sensor_id) REFERENCES sensors(id),
    INDEX idx_battery_alerts_sensor_id (sensor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
