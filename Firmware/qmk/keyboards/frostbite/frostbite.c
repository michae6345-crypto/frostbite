// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"

/* Bootmagic: hold Approve (row 2, col 0) AND Stop (row 2, col 2) while
 * plugging in the USB cable to clear EEPROM and jump to the UF2 bootloader.
 * Needing two keys avoids accidental flashes from a single stuck switch. */
bool bootmagic_should_reset(void) {
    matrix_row_t row2 = matrix_get_row(2);
    return (row2 & (1 << 0)) && (row2 & (1 << 2));
}

#ifdef OLED_ENABLE
/* The OLED header sits at the right (+x) end of the PCB. If text shows up
 * upside down on your module, add `#define FROSTBITE_OLED_FLIP` to config.h
 * (or build with OPT_DEFS += -DFROSTBITE_OLED_FLIP) and reflash. */
oled_rotation_t oled_init_kb(oled_rotation_t rotation) {
#    ifdef FROSTBITE_OLED_FLIP
    rotation = OLED_ROTATION_180;
#    endif
    return oled_init_user(rotation);
}
#endif
