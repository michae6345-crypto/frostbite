# Firmware desk tests

`run.sh` builds two test programs with clang (ASan + UBSan) and runs both. Each adds a fake clock (`stub/`) and an SSD1306
GDDRAM model behind stubbed I2C (`panel.c`), and links QMK's `drivers/oled/oled_driver.c`, so it shows what reaches the
panel as well as what is in the frame buffer.

- `harness.c` `#include`s the real `keymaps/default/keymap.c`.
- `bringup_test.c` `#include`s the real `keymaps/bringup/keymap.c`.

`proto_test.py` drives the `harness` binary with the real host `device.py` and `Daemon`, and reads the status words from
`design.json`.

Needs clang and `~/qmk_firmware`. Nothing here runs on hardware. `verify/run.sh` runs these as `G6.firmware_harness` and
`G6.oled_strip_panel`. That check matches the `PASS F1 ...` lines by text; F1 is the OLED strip starvation finding in
`docs/audit/firmware.md`.
