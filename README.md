# Lab controller

ESPHome controller for an ESP32-2432S028R (ILI9341, XPT2046 resistive touch). The screen is 320×240 landscape, with temperature and relative humidity above four 70×70 scene buttons.

The initial MIPI SPI configuration produced scrambled pixels at both 90° and 270°. Brent confirmed that switching to `ili9xxx` / `ILI9341`, an 8-bit full-frame buffer, and 10 MHz SPI removed the scrambling; the individual cause was not isolated. The 90° and 270° configurations still appeared portrait and clipped on this device. Brent confirmed correct landscape orientation and no scrambling with explicit 320×240 dimensions and rotation 0°. His photo showed red rendered blue and gold rendered cyan; Brent confirmed `color_order: RGB` corrected the colors. Keep the working geometry/driver/buffer/clock settings. Touch axes were then swapped and both mirrored, with calibration ranges exchanged. Serial logs now show all four button hits requesting the correct scenes while Home Assistant is connected. Brent confirmed scene execution after enabling Home Assistant action permission. The display was subsequently flipped to rotation 180° at his request; touch retains `swap_xy: true` with both mirrors now false. Brent confirmed the final flipped display and buttons work. Precise edge calibration has not been measured.

| Button | Home Assistant scene |
| --- | --- |
| White | `scene.bright_white_lab` |
| Gold | `scene.golden_lab` |
| Red | `scene.red_lab` |
| Black | `scene.night_lab` |

Readings come from `sensor.desk_temperature` and `sensor.desk_humidity`. Temperature uses the entity's `unit_of_measurement`: Fahrenheit is converted to Celsius; unknown units are not guessed. Unavailable readings show `--`. When no Home Assistant state subscriber is connected, both readings show `--` and the screen shows `HA offline`. Buttons send scene requests, not confirmations of the lights' state.

## Build

Tested configuration targets ESPHome 2026.10.0, Python 3.12, and ESP-IDF. Install with `uv tool install --python 3.12 esphome==2026.10.0`. Fonts download from Google Fonts during the first validation/build.

Local `secrets.yaml` holds `wifi_ssid`, `wifi_password`, `api_key`, and `ota_password`. It was created from the existing Wi-Fi credentials with new API/OTA credentials and mode 0600. Do not publish secrets, factory dumps, build output, or firmware binaries: they can contain credentials. `.gitignore` excludes these; this directory is not currently a Git repository.

```sh
esphome config lab-controller.yaml
"$(uv tool dir)/esphome/bin/python" test_controller.py
esphome compile lab-controller.yaml
```

The self-check executes the actual drawing lambda with a recording display and checks scene mappings, square touch areas, labels, colors, temperature conversion, invalid readings, and disconnected behavior. It does not test real hardware.

## Flash and connect

The initial firmware was flashed over USB with hash verification. Brent explicitly waived a backup because the previous code was disposable. The existing `factory_stuff/cyd_factory.bin` was not verified against the connected device. Flashing replaces firmware and may change the partition layout.

Wi-Fi connected using DHCP; an encrypted API connection from this computer verified the device name and ESPHome version. Brent subsequently confirmed Home Assistant readings, correct display orientation/colors, and working scene buttons.

Upload and logs:

```sh
esphome upload lab-controller.yaml --device YOUR_SERIAL_PORT
esphome logs lab-controller.yaml --device YOUR_SERIAL_PORT
```

In Home Assistant, add the discovered **Lab Controller** through the ESPHome integration (or use its LAN IP and port 6053). Enter `api_key` from the local secrets file. In the integration's device configuration, enable **Allow the device to perform Home Assistant actions**. Without this permission, sensor readings can work while scene buttons do not.

Home Assistant connects to the ESP32 over the LAN; its public HTTPS URL is not a firmware endpoint. The Home Assistant host must be able to reach the device's native API port. mDNS discovery may not cross network segments, so use the LAN IP if discovery fails.

## Hardware acceptance

After flashing, verify landscape orientation, correct colors, both live readings, and each button's scene. Check taps at the four screen corners in serial logs before enabling scene actions. The starting calibration is from the CYD reference example, not a measurement of this panel. Adjust `touchscreen.calibration` and `transform` from the observed raw and mapped coordinates if needed. Test button centers and edges; gaps must not activate scenes. An 8-pixel gap separates adjacent buttons.

Disconnect Home Assistant and confirm the offline display; reconnect and confirm readings return. Confirm a held button does not repeatedly activate its scene. Brent confirmed display rendering, live readings, and scene execution after enabling Home Assistant action permission. Wi-Fi and the encrypted native API were verified after flashing. Exact corner/edge calibration and offline/reconnect acceptance checks remain unverified.

Hardware references:
- [CYD touch example](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/Examples/ESPHome/4-TouchDemo/yellowtft1.yaml)
- [ESPHome MIPI SPI display](https://esphome.io/components/display/mipi_spi/)
- [ESPHome XPT2046 touchscreen](https://esphome.io/components/touchscreen/xpt2046/)
