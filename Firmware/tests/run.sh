#!/bin/bash
# Firmware desk harness: the real keymaps and QMK's real OLED driver on this Mac, under ASan and UBSan.
# Usage: run.sh [output dir] [keymap.c]     QMK_HOME defaults to ~/qmk_firmware
# keymap.c replaces the default keymap. The bring-up keymap always runs too.
# Exit: non-zero on any FAIL, 2 if it does not build.
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
clang "${CF[@]}" harness.o oled.o panel.o fb.o -o harness || exit 2
clang "${CF[@]}" '-DQMK_KEYBOARD_H="stub_qmk.h"' "-DKEYMAP_FILE=\"$K/keymaps/bringup/keymap.c\"" -c "$A/bringup_test.c" -o bringup_test.o || exit 2
clang "${CF[@]}" bringup_test.o oled.o panel.o fb.o -o bringup_test || exit 2
./harness
rc=$?
./bringup_test
rc2=$?
[ $rc -ne 0 ] && exit $rc
exit $rc2
