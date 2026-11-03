#!/bin/bash
# Firmware desk harness: the real keymap.c and QMK's real OLED driver on this Mac, under ASan and UBSan.
# Usage: run.sh [output dir] [keymap.c]     QMK_HOME defaults to ~/qmk_firmware
# Exit: harness exit code (non-zero on any FAIL), 2 if it does not build.
A=$(cd "$(dirname "$0")" && pwd)
K=$(cd "$A/../qmk/keyboards/frostbite" && pwd)
Q=${QMK_HOME:-$HOME/qmk_firmware}
OUT=${1:-$(mktemp -d)}
KM=${2:-$K/keymaps/default/keymap.c}
mkdir -p "$OUT"
CF=(-std=gnu11 -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=undefined "-I$A/stub" "-I$Q/drivers/oled" "-I$Q"
    -include "$K/config.h" -DOLED_TRANSPORT_I2C -DOLED_ENABLE -Wall -Wno-unused-function -Wno-unused-variable
    -Wno-unused-const-variable -Wno-macro-redefined)
cd "$OUT" || exit 2
clang "${CF[@]}" '-DQMK_KEYBOARD_H="stub_qmk.h"' "-DKEYMAP_FILE=\"$KM\"" -c "$A/harness.c" -o harness.o || exit 2
clang "${CF[@]}" -c "$Q/drivers/oled/oled_driver.c" -o oled.o || exit 2
clang "${CF[@]}" -c "$A/panel.c" -o panel.o || exit 2
clang "${CF[@]}" -c "$K/frostbite.c" -o fb.o || exit 2
L8=
clang "${CF[@]}" -D__arm__=1 -c "$A/stub/lib/lib8tion/lib8tion.c" -o l8.o 2>/dev/null && L8=l8.o
clang "${CF[@]}" harness.o oled.o panel.o fb.o $L8 -o harness || exit 2
exec ./harness
