// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"

/* Bootmagic needs Approve (row 2, col 0) and Stop (row 2, col 2) held together,
 * so one stuck switch cannot drop the pad into the bootloader. Replaces the
 * single-key default that keyboard.json names. */
bool bootmagic_should_reset(void) {
    matrix_row_t row2 = matrix_get_row(2);
    return (row2 & (1 << 0)) && (row2 & (1 << 2));
}

#ifdef OLED_ENABLE
oled_rotation_t oled_init_kb(oled_rotation_t rotation) {
#    ifdef FROSTBITE_OLED_FLIP
    rotation = OLED_ROTATION_180;
#    endif
    return oled_init_user(rotation);
}
#endif
