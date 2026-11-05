// Copyright 2026 Michael Tarekegn
// SPDX-License-Identifier: GPL-2.0-or-later

#include QMK_KEYBOARD_H
#include "raw_hid.h"
#include <string.h>

#define NUM_SLOTS 6
#define NUM_KEYS 9
#define LINE_CHARS 21
#define REPORT_BYTES 32

#define PROTOCOL_VERSION 1
#define HOST_TIMEOUT_MS 5000
#define OLED_SLEEP_MS (10UL * 60UL * 1000UL)

enum cmd {
    CMD_SET_SLOT     = 0x01,
    CMD_SET_ALL      = 0x02,
    CMD_OLED_LINE    = 0x03,
    CMD_PING         = 0x05,
    CMD_SET_SELECTED = 0x06,
    EVT_KEY          = 0x81,
    EVT_ENCODER      = 0x82,
};

enum status { ST_IDLE = 0, ST_RUN = 1, ST_DONE = 2, ST_NEEDS = 3, ST_ERROR = 4, ST_COUNT };

#define KEY_TALK 7

static const char *const status_name[ST_COUNT] = {"IDLE", "RUN", "DONE", "WAIT", "ERR"};
static const char status_letter[ST_COUNT] = {'-', 'R', 'D', '?', '!'};

static uint8_t  slot_status[NUM_SLOTS];
static bool     statuses_received;
static uint8_t  selected_slot;
static char     host_line[2][LINE_CHARS + 1];

static bool     ever_pinged;
static uint32_t last_ping;

static uint32_t last_activity;
static bool     oled_asleep;

static bool     key_host[NUM_KEYS];
static bool     key_hold_sent[NUM_KEYS];
static uint16_t key_press_time[NUM_KEYS];

// clang-format off
// only used when the host script isn't running
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_ortho_3x3(
        KC_F13, KC_F14, KC_F15,
        KC_F16, KC_F17, KC_F18,
        KC_F19, KC_F20, KC_ESC
    )
};
// clang-format on

static bool host_mode(void) {
    return ever_pinged && timer_elapsed32(last_ping) < HOST_TIMEOUT_MS;
}

// resets the oled sleep timer. pings don't count
static void wake(void) {
    last_activity = timer_read32();
    oled_asleep   = false;
}

static void set_status(uint8_t slot, uint8_t st) {
    if (slot >= NUM_SLOTS) return;
    if (st >= ST_COUNT) st = ST_IDLE;
    if (slot_status[slot] == st) return;
    slot_status[slot] = st;
    wake();
}

static void send_report(uint8_t a, uint8_t b, uint8_t c) {
    uint8_t buf[REPORT_BYTES];
    memset(buf, 0, sizeof(buf));
    buf[0] = a;
    buf[1] = b;
    buf[2] = c;
    raw_hid_send(buf, sizeof(buf));
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    uint8_t row = record->event.key.row;
    uint8_t col = record->event.key.col;
    if (row >= MATRIX_ROWS || col >= MATRIX_COLS) return true;
    uint8_t idx = row * MATRIX_COLS + col;

    wake();

    if (record->event.pressed) {
        if (host_mode()) {
            key_host[idx]       = true;
            key_hold_sent[idx]  = false;
            key_press_time[idx] = timer_read();
            return idx == KEY_TALK; // talk still holds f20 for push to talk
        }
        key_host[idx] = false;
        return true;
    }

    if (key_host[idx]) {
        key_host[idx] = false;
        if (!key_hold_sent[idx]) send_report(EVT_KEY, idx, 1);
        return idx == KEY_TALK;
    }
    return true;
}

bool encoder_update_user(uint8_t index, bool clockwise) {
    wake();
    if (host_mode()) {
        selected_slot = clockwise ? (selected_slot + 1) % NUM_SLOTS : (selected_slot + NUM_SLOTS - 1) % NUM_SLOTS;
        send_report(EVT_ENCODER, clockwise ? 0x01 : 0xFF, selected_slot);
    } else {
        tap_code_delay(clockwise ? KC_VOLU : KC_VOLD, 10);
    }
    return false;
}

void raw_hid_receive(uint8_t *data, uint8_t length) {
    if (length < 1) return;

    switch (data[0]) {
        case CMD_SET_SLOT:
            if (length >= 3 && data[1] < NUM_SLOTS) {
                set_status(data[1], data[2]);
                statuses_received = true;
            }
            break;

        case CMD_SET_ALL:
            if (length >= 1 + NUM_SLOTS) {
                for (uint8_t i = 0; i < NUM_SLOTS; i++) set_status(i, data[1 + i]);
                statuses_received = true;
            }
            break;

        case CMD_OLED_LINE:
            if (length >= 3 && data[1] < 2) {
                uint8_t len = data[2];
                if (len > LINE_CHARS) len = LINE_CHARS;
                if (len > length - 3) len = length - 3;
                char line[LINE_CHARS + 1];
                for (uint8_t i = 0; i < len; i++) {
                    char c  = (char)data[3 + i];
                    line[i] = (c >= 0x20 && c < 0x7f) ? c : ' ';
                }
                line[len] = '\0';
                memcpy(host_line[data[1]], line, len + 1);
            }
            break;

        case CMD_PING:
            ever_pinged = true;
            last_ping   = timer_read32();
            send_report(CMD_PING, PROTOCOL_VERSION, selected_slot);
            break;

        case CMD_SET_SELECTED:
            if (length >= 2 && data[1] < NUM_SLOTS) selected_slot = data[1];
            break;

        default:
            break;
    }
}

void housekeeping_task_user(void) {
    for (uint8_t i = 0; i < NUM_KEYS; i++) {
        if (key_host[i] && !key_hold_sent[i] && timer_elapsed(key_press_time[i]) >= FROSTBITE_HOLD_MS) {
            key_hold_sent[i] = true;
            send_report(EVT_KEY, i, 2);
        }
    }

    if (ever_pinged && timer_elapsed32(last_ping) >= HOST_TIMEOUT_MS) ever_pinged = false;
}

static void write_row(uint8_t row, const char *s) {
    char buf[LINE_CHARS + 1];
    uint8_t i = 0;
    for (; i < LINE_CHARS && s[i]; i++) buf[i] = s[i];
    for (; i < LINE_CHARS; i++) buf[i] = ' ';
    buf[LINE_CHARS] = '\0';
    oled_set_cursor(0, row);
    oled_write(buf, false);
}

static uint8_t append(char *dst, uint8_t pos, const char *s) {
    while (*s && pos < 31) dst[pos++] = *s++;
    dst[pos] = '\0';
    return pos;
}

static void build_summary(char *dst, bool compact) {
    static const uint8_t     order[4]  = {ST_RUN, ST_NEEDS, ST_DONE, ST_ERROR};
    static const char *const labels[4] = {"run", "wait", "done", "err"};
    uint8_t                  pos       = 0;
    dst[0]                             = '\0';
    for (uint8_t j = 0; j < 4; j++) {
        uint8_t n = 0;
        for (uint8_t i = 0; i < NUM_SLOTS; i++)
            if (slot_status[i] == order[j]) n++;
        if (!n) continue;
        if (pos) pos = append(dst, pos, " ");
        char num[2] = {(char)('0' + n), '\0'};
        pos         = append(dst, pos, num);
        if (!compact) pos = append(dst, pos, " ");
        pos = append(dst, pos, labels[j]);
    }
    if (!pos) append(dst, 0, "all idle");
}

bool oled_task_user(void) {
    if (timer_elapsed32(last_activity) > OLED_SLEEP_MS) oled_asleep = true;
    if (oled_asleep) {
        oled_off();
        return false;
    }
    oled_on();

    bool hm = host_mode();
    char line[32];

    if (!hm) {
        write_row(0, "FROSTBITE   no host");
    } else if (host_line[0][0]) {
        write_row(0, host_line[0]);
    } else {
        uint8_t st = slot_status[selected_slot];
        uint8_t p  = append(line, 0, "slot ");
        char    n[2] = {(char)('1' + selected_slot), '\0'};
        p          = append(line, p, n);
        p          = append(line, p, "  ");
        append(line, p, status_name[st]);
        write_row(0, line);
    }

    if (!hm) {
        write_row(1, "F13-F20 Esc  knob=vol");
    } else if (host_line[1][0]) {
        write_row(1, host_line[1]);
    } else if (statuses_received) {
        build_summary(line, false);
        if (strlen(line) > LINE_CHARS) build_summary(line, true);
        write_row(1, line);
    } else {
        write_row(1, "turn knob: pick slot");
    }

    // divider. don't write text on this row, it starves row 3 of oled updates
    for (uint8_t x = 0; x < 126; x += 3) oled_write_pixel(x, 19, true);

    oled_set_cursor(0, 3);
    for (uint8_t i = 0; i < NUM_SLOTS; i++) {
        uint8_t st      = hm ? slot_status[i] : ST_IDLE;
        char    cell[3] = {(char)('1' + i), status_letter[st], '\0'};
        oled_write(cell, hm && i == selected_slot);
        oled_write_char(' ', false);
    }
    oled_write(hm ? "HID" : "KBD", false);

    return false;
}

void keyboard_post_init_user(void) {
    wake();
}

void suspend_wakeup_init_user(void) {
    wake();
}
