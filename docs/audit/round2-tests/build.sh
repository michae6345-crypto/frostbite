#!/bin/bash
# Usage: build.sh <output dir>. Builds fw_e2e against the unmodified keymap.c, harness.c and QMK OLED driver.
A=$(cd "$(dirname "$0")" && pwd); R=$(cd "$A/../../.." && pwd); T=$R/Firmware/tests; K=$R/Firmware/qmk/keyboards/frostbite; Q=${QMK_HOME:-$HOME/qmk_firmware}
OUT=$1; mkdir -p "$OUT"; cd "$OUT" || exit 2
CF=(-std=gnu11 -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=undefined "-I$T/stub" "-I$Q/drivers/oled" "-I$Q" -include "$K/config.h" -DOLED_TRANSPORT_I2C -DOLED_ENABLE -w)
clang "${CF[@]}" '-DQMK_KEYBOARD_H="stub_qmk.h"' "-DKEYMAP_FILE=\"$K/keymaps/default/keymap.c\"" "-DHARNESS_FILE=\"$T/harness.c\"" -c "$A/fw_e2e.c" -o e2e.o || exit 2
clang "${CF[@]}" -c "$Q/drivers/oled/oled_driver.c" -o oled.o || exit 2
clang "${CF[@]}" -c "$T/panel.c" -o panel.o || exit 2
clang "${CF[@]}" -c "$K/frostbite.c" -o fb.o || exit 2
L8=; clang "${CF[@]}" -D__arm__=1 -c "$T/stub/lib/lib8tion/lib8tion.c" -o l8.o 2>/dev/null && L8=l8.o
clang "${CF[@]}" e2e.o oled.o panel.o fb.o $L8 -o fw_e2e || exit 2
echo built "$OUT/fw_e2e"
