"""Constants for the Anova Legacy BLE integration."""

from datetime import timedelta

DOMAIN = "anova_legacy_ble"

CONF_DEVICE_NAME = "device_name"

SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

UPDATE_INTERVAL = timedelta(seconds=30)
FAILURE_GRACE_POLLS = 2

CMD_GET_ID = "get id card"
CMD_STATUS = "status"
CMD_READ_UNIT = "read unit"
CMD_READ_TEMP = "read temp"
CMD_READ_TARGET_TEMP = "read set temp"
CMD_READ_TIMER = "read timer"
CMD_START = "start"
CMD_STOP = "stop"
CMD_START_TIMER = "start time"
CMD_STOP_TIMER = "stop time"
CMD_CLEAR_ALARM = "clear alarm"
CMD_VERSION = "version"

PLATFORMS = ["sensor", "number", "switch", "climate", "select", "button"]
