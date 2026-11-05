// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Frostbite 9 bring-up firmware. Checks each key, the dial direction and the OLED.
//
// For the first 3 s after boot every OLED pixel is on, so a dead pixel or line
// shows. Then the screen reads:
//
//   BRINGUP  keys 3/9       distinct keys seen so far
//   seen 12..5....          keys 1-9 in design.json keys[] order, dot = not yet
//   key: r1 c1 Agent 5      last key pressed, its matrix position and name
//   knob: 4 CW              count, then the direction of the last click
//
// Keys send the same fallback keycodes as the default keymap. The knob does not
// change the volume, so it can be turned freely.

#include QMK_KEYBOARD_H
#include <string.h>

#define NUM_KEYS 9
#define LINE_CHARS 21
#define PIXEL_TEST_MS 3000

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_ortho_3x3(
        KC_F13, KC_F14, KC_F15,
        KC_F16, KC_F17, KC_F18,
        KC_F19, KC_F20, KC_ESC
    )
};
// clang-format on

static const char *const key_name[NUM_KEYS] = {"Agent 1", "Agent 2", "Agent 3", "Agent 4", "Agent 5", "Agent 6", "Approve", "Talk", "Stop"};

static uint32_t boot_time;
static bool     pixels_filled, pixel_test_done;
static uint16_t keys_seen; /* bit n = key index n */
static int8_t   last_key = -1;
static int16_t  enc_count;
static bool     enc_moved, enc_cw;

void keyboard_post_init_user(void) {
    boot_time = timer_read32();
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    uint8_t row = record->event.key.row;
    uint8_t col = record->event.key.col;
    if (record->event.pressed && row < MATRIX_ROWS && col < MATRIX_COLS) {
        last_key = (int8_t)(row * MATRIX_COLS + col);
        keys_seen |= (uint16_t)(1U << last_key);
    }
    return true;
}

bool encoder_update_user(uint8_t index, bool clockwise) {
    enc_count += clockwise ? 1 : -1;
    enc_moved = true;
    enc_cw    = clockwise;
    return false; /* no volume in the bring-up build */
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
    char    buf[LINE_CHARS + 1];
    uint8_t i = 0;
    for (; i < LINE_CHARS && s[i]; i++) buf[i] = s[i];
    for (; i < LINE_CHARS; i++) buf[i] = ' ';
    buf[LINE_CHARS] = '\0';
    oled_set_cursor(0, row);
    oled_write(buf, false);
}

bool oled_task_user(void) {
    if (!pixel_test_done) {
        if (!pixels_filled) {
            for (uint16_t i = 0; i < OLED_MATRIX_SIZE; i++) oled_write_raw_byte((char)0xFF, i);
            pixels_filled = true;
        }
        if (timer_elapsed32(boot_time) < PIXEL_TEST_MS) return false;
        pixel_test_done = true;
        oled_clear(); /* text rows stop short of the last two columns */
    }

    char    line[LINE_CHARS + 1];
    uint8_t count = 0;

    strcpy(line, "seen ");
    char *p = line + strlen(line);
    for (uint8_t i = 0; i < NUM_KEYS; i++) {
        bool seen = keys_seen & (1U << i);
        *p++      = seen ? (char)('1' + i) : '.';
        if (seen) count++;
    }
    *p = '\0';
    write_padded(1, line);

    strcpy(line, "BRINGUP  keys ");
    strcat_num(line, count);
    strcat(line, "/9");
    write_padded(0, line);

    if (last_key < 0) {
        write_padded(2, "key: -");
    } else {
        strcpy(line, "key: r");
        strcat_num(line, (uint16_t)(last_key / MATRIX_COLS));
        strcat(line, " c");
        strcat_num(line, (uint16_t)(last_key % MATRIX_COLS));
        strcat(line, " ");
        strcat(line, key_name[last_key]);
        write_padded(2, line);
    }

    if (!enc_moved) {
        write_padded(3, "knob: turn it");
    } else {
        strcpy(line, "knob: ");
        if (enc_count < 0) {
            strcat(line, "-");
            strcat_num(line, (uint16_t)(-enc_count));
        } else {
            strcat_num(line, (uint16_t)enc_count);
        }
        strcat(line, enc_cw ? " CW" : " CCW");
        write_padded(3, line);
    }
    return false;
}
