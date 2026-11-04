// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Frostbite 9 bring-up firmware. Lights the 13 SK6812s one at a time in chain
// order, red, green, blue, white, and shows "LED TEST n/13" on the OLED. If LED n
// lights but n+1 never does, look at LED n's DOUT and LED n+1's DIN and power.
//
// The OLED also shows the last key pressed and an encoder count. Keys send the
// same fallback keycodes as the default keymap.

#include QMK_KEYBOARD_H
#include <string.h>

#define NUM_LEDS 13
#define STEP_MS 350
#define TEST_LEVEL 90 /* keep the XIAO's USB current modest */

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_ortho_3x3(
        KC_F13, KC_F14, KC_F15,
        KC_F16, KC_F17, KC_F18,
        KC_F19, KC_F20, KC_ESC
    )
};
// clang-format on

static const char *const colour_name[4] = {"red", "green", "blue", "white"};

static uint32_t step_timer;
static uint8_t  step; /* 0 .. NUM_LEDS*4-1 */
static int16_t  enc_count;
static int8_t   last_row = -1, last_col = -1;

void keyboard_post_init_user(void) {
    rgb_matrix_enable_noeeprom();
    rgb_matrix_mode_noeeprom(RGB_MATRIX_SOLID_COLOR);
    rgb_matrix_sethsv_noeeprom(0, 0, 0);
    step_timer = timer_read32();
}

void housekeeping_task_user(void) {
    if (timer_elapsed32(step_timer) >= STEP_MS) {
        step_timer = timer_read32();
        step       = (step + 1) % (NUM_LEDS * 4);
    }
}

bool rgb_matrix_indicators_user(void) {
    uint8_t led    = step / 4;
    uint8_t colour = step % 4;
    rgb_matrix_set_color_all(0, 0, 0);
    switch (colour) {
        case 0: rgb_matrix_set_color(led, TEST_LEVEL, 0, 0); break;
        case 1: rgb_matrix_set_color(led, 0, TEST_LEVEL, 0); break;
        case 2: rgb_matrix_set_color(led, 0, 0, TEST_LEVEL); break;
        default: rgb_matrix_set_color(led, TEST_LEVEL, TEST_LEVEL, TEST_LEVEL); break;
    }
    return false;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (record->event.pressed) {
        last_row = record->event.key.row;
        last_col = record->event.key.col;
    }
    return true;
}

bool encoder_update_user(uint8_t index, bool clockwise) {
    enc_count += clockwise ? 1 : -1;
    return false; /* no volume in the test build */
}

static void strcat_num(char *dst, uint16_t n) {
    char    tmp[6];
    uint8_t i = 0;
    do {
        tmp[i++] = (char)('0' + n % 10);
        n /= 10;
    } while (n && i < sizeof(tmp));
    char *p = dst + strlen(dst);
    while (i) *p++ = tmp[--i];
    *p = '\0';
}

static void write_padded(uint8_t row, const char *s) {
    char    buf[22];
    uint8_t i = 0;
    for (; i < 21 && s[i]; i++) buf[i] = s[i];
    for (; i < 21; i++) buf[i] = ' ';
    buf[21] = '\0';
    oled_set_cursor(0, row);
    oled_write(buf, false);
}

bool oled_task_user(void) {
    uint8_t led    = step / 4;
    uint8_t colour = step % 4;
    char    line[22];

    strcpy(line, "LED TEST ");
    strcat_num(line, led + 1);
    strcat(line, "/13");
    write_padded(0, line);

    strcpy(line, "colour: ");
    strcat(line, colour_name[colour]);
    write_padded(1, line);

    if (last_row < 0) {
        write_padded(2, "key: -");
    } else {
        strcpy(line, "key: r");
        strcat_num(line, (uint16_t)last_row);
        strcat(line, " c");
        strcat_num(line, (uint16_t)last_col);
        write_padded(2, line);
    }

    strcpy(line, "knob: ");
    if (enc_count < 0) {
        strcat(line, "-");
        strcat_num(line, (uint16_t)(-enc_count));
    } else {
        strcat_num(line, (uint16_t)enc_count);
    }
    write_padded(3, line);
    return false;
}
