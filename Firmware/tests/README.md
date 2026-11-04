# Firmware desk tests

`run.sh` builds `harness.c` with clang (ASan + UBSan). It `#include`s the real `keymaps/default/keymap.c`, links QMK's
`drivers/oled/oled_driver.c` and lib8tion, and adds a fake clock (`stub/`) and an SSD1306 GDDRAM model behind stubbed I2C
(`panel.c`), so it shows what reaches the panel as well as what is in the frame buffer. `proto_test.py` drives the same
binary with the real host `device.py` and `Daemon`.

`stub/lib/lib8tion` is QMK's copy with the AVR-only routines removed from `trig8.h` so it builds on the host.
Needs clang and `~/qmk_firmware`. Nothing here runs on hardware. `verify/run.sh` runs both as `G6.firmware_harness` and
`G6.oled_strip_panel`. That check matches the `PASS F1 ...` lines by text; F1 is the OLED strip starvation finding in
`docs/audit/firmware.md`.
