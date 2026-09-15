# Anova Legacy BLE for Home Assistant

Best-effort local Home Assistant integration for the **original Anova Precision Cooker** generation using Bluetooth Low Energy. It is based on Anova Culinary's published A2/A3 BLE protocol.

## What it supports

- Current water temperature
- Target temperature
- Start / stop cooking
- Timer value
- Set timer
- Start / stop timer
- Celsius / Fahrenheit selection
- Climate entity
- Automatic model detection from `get id card` when supported
- Home Assistant's shared Bluetooth stack, including **connectable ESPHome Bluetooth proxies**

The known protocol uses:

- Service UUID: `0000ffe0-0000-1000-8000-00805f9b34fb`
- Characteristic UUID: `0000ffe1-0000-1000-8000-00805f9b34fb`
- ASCII commands terminated by carriage return (`\r`)
- Responses delivered as notifications on the same characteristic

## Installation

### Manual installation

1. Copy the folder `custom_components/anova_legacy_ble` into your Home Assistant configuration directory so you have `/config/custom_components/anova_legacy_ble/manifest.json`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**.
4. Search for **Anova Legacy BLE**.

### HACS custom repository

Add this repository under **HACS → Integrations → Custom repositories**, choosing **Integration** as the repository type. Public repository visibility is recommended for straightforward HACS installation.

## Bluetooth setup / pairing

### Recommended first attempt: do NOT pre-pair

Anova's published Python reference client connects directly over BLE and does not explicitly pair/bond first.

1. Put the cooker in water high enough to satisfy its minimum-water sensor.
2. Plug the cooker in and power it on.
3. Press the **Bluetooth button** on the Anova. On the original cooker the Bluetooth indicator should turn blue/blink while it is discoverable.
4. Keep your Home Assistant Bluetooth adapter or a connectable ESPHome Bluetooth proxy nearby.
5. In Home Assistant add **Anova Legacy BLE**.
6. If Home Assistant has seen the advertisement, select the Anova from the list.
7. Finish setup while the cooker is still powered on and advertising.

The first refresh opens a BLE connection and reads the cooker. If setup remains in a retrying state, leave the Anova powered on and press its Bluetooth button again.

### ESPHome Bluetooth proxy

A current ESP32 ESPHome Bluetooth proxy can make active BLE connections. The integration asks Home Assistant for the best **connectable** path to the cooker rather than opening its own scanner, so a proxy can be used.

Example ESPHome fragment:

```yaml
esp32_ble_tracker:

bluetooth_proxy:
  active: true
```

You do not configure the Anova MAC address in ESPHome. Home Assistant routes the BLE connection through the proxy automatically.

### Do I need a Bluetooth PIN?

Probably not. Historical Anova community guidance for the 2014 BLE cooker says it is meant to be connected from inside an app rather than paired from the operating system's normal Bluetooth-device screen. Anova's A2/A3 Python reference client also connects directly without performing a bonding step.

A third-party Windows client documents PIN `0000` for its pairing workflow, so firmware/OS variations may exist. For this integration, do not start by pairing it in Windows/iOS/Android settings. Put the cooker in discoverable mode and let Home Assistant connect directly. If debug logs show an authentication or insufficient-encryption error, bonding support may need to be added.

## Entities

Typical entities include:

- `climate.<device>_cooker`
- `sensor.<device>_water_temperature`
- `sensor.<device>_target_temperature`
- `sensor.<device>_timer`
- `sensor.<device>_cooker_id`
- `number.<device>_target_temperature_setting`
- `number.<device>_timer_setting`
- `switch.<device>_cooking`
- `select.<device>_temperature_unit`
- buttons for starting/stopping the timer

The exact entity IDs depend on the device name Home Assistant assigns.

## How the integration communicates

Every update uses one short BLE connection:

1. Home Assistant selects the best adapter/proxy that can reach the device.
2. The integration connects.
3. It subscribes to notifications on `FFE1`.
4. It sends read commands such as `get id card`, `read unit`, `status`, `read set temp`, `read temp`, and `read timer`.
5. It disconnects.

Control operations similarly connect, send a command, and disconnect. This avoids permanently occupying an ESPHome proxy connection slot and avoids blocking the official app for long periods.

## Debug logging

Add this to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.anova_legacy_ble: debug
    bleak_retry_connector: debug
```

Restart Home Assistant, power on the cooker, press its Bluetooth button, then reload the integration.

Useful log messages include:

- whether HA can find a connectable route to the cooker
- BLE connection errors
- `Anova TX` commands
- `Anova RX` responses

## Known uncertainties

This is a best-effort initial implementation and has not yet been broadly tested across original Anova firmware revisions.

1. Some original firmware revisions may require legacy bonding/PIN `0000` before allowing GATT access.
2. Anova firmware may vary in whether write commands return acknowledgements. This integration does not require an acknowledgement for writes.
3. `read timer` response formatting varies in old community implementations; the parser extracts the first numeric value.
4. The published model detection treats IDs beginning with `anova f56-` as the 900 W BT/Wi-Fi model and other IDs as the 800 W Bluetooth model.
5. The first refresh currently requires the cooker to be reachable; if it is off during setup, Home Assistant will keep retrying the config entry.

## Protocol source

The implementation is based primarily on Anova Culinary's published `developer-project-a2a3` reference client for the original 800 W Bluetooth-only and 900 W Bluetooth/Wi-Fi cookers.
