// Copyright 2026 Michael Tarekegn
// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"

// hold approve + stop while plugging in, one stuck key can't enter the bootloader
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
