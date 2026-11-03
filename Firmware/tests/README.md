# Firmware desk tests

`run.sh` builds `harness.c` with clang (ASan + UBSan). It `#include`s the real `keymaps/default/keymap.c`, links QMK's real
`drivers/oled/oled_driver.c` and lib8tion, and adds a fake clock (`stub/`) and an SSD1306 GDDRAM model behind stubbed I2C (`panel.c`).
So it shows what reaches the panel, not only what is in the frame buffer. `proto_test.py` drives the same binary with the real host
`device.py` and `Daemon`. Needs clang and `~/qmk_firmware`. Nothing here runs on hardware. `verify/run.sh` runs both as
`G6.firmware_harness` and `G6.oled_strip_panel` (the F1 regression from `docs/audit/firmware.md`).
