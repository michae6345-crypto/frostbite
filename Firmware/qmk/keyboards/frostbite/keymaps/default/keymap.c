// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Frostbite 9 default keymap: agent dashboard over Raw HID, with a plain
// keyboard fallback when no host app is talking to the pad.
//
// Everything here follows design.json ("protocol" section). Summary:
//   host -> device  0x01 SET_SLOT  [0x01, slot, status]
//                   0x02 SET_ALL   [0x02, s0..s5]
//                   0x03 OLED_LINE [0x03, line 0-1, len, <=21 ASCII]
//                   0x04 SET_GLOW  [0x04, r, g, b, brightness]
//                   0x05 PING      [0x05] -> reply [0x05, 1, selected_slot]
//                   0x06 SET_SELECTED [0x06, slot]
//   device -> host  0x81 KEY       [0x81, key 0-8, 1=tap 2=hold]
//                   0x82 ENCODER   [0x82, 1=cw 0xFF=ccw, selected_slot]
//
// Talk (key 7) always sends F20, held while held, in both modes; in host mode
// it also sends its KEY event. hidapi's leading 0x00 report ID is consumed by
// the OS (the raw HID descriptor has no report IDs), so data[0] is the command.
//
// Host mode is active while a PING arrived in the last 5 s. Otherwise the
// keys send the keycodes in the keymap below (F13-F18, F19, F20, Esc) and the
// encoder sends volume up/down.

#include QMK_KEYBOARD_H
#include "raw_hid.h"
#include "lib/lib8tion/lib8tion.h"
#include <string.h>

/* ------------------------------------------------------------------------ */
/* Constants                                                                 */
/* ------------------------------------------------------------------------ */

#define NUM_SLOTS 6
#define NUM_KEYS 9
#define NUM_LEDS 13
#define LINE_CHARS 21
#define REPORT_BYTES 32 /* design.json firmware.raw_hid.report_bytes */

#define PROTOCOL_VERSION 1
#define HOST_TIMEOUT_MS 5000
#define OLED_SLEEP_MS (10UL * 60UL * 1000UL)
#define FADE_MS 300
#define FALLBACK_FADE_MS 1500

#ifndef FROSTBITE_HOLD_MS
#    define FROSTBITE_HOLD_MS 400
#endif

enum cmd {
    CMD_SET_SLOT     = 0x01,
    CMD_SET_ALL      = 0x02,
    CMD_OLED_LINE    = 0x03,
    CMD_SET_GLOW     = 0x04,
    CMD_PING         = 0x05,
    CMD_SET_SELECTED = 0x06,
    EVT_KEY          = 0x81,
    EVT_ENCODER      = 0x82,
};

enum status { ST_IDLE = 0, ST_RUN = 1, ST_DONE = 2, ST_NEEDS = 3, ST_ERROR = 4, ST_COUNT };

/* key index (design.json keys[] order, row * 3 + col) -> LED index */
static const uint8_t key_led[NUM_KEYS] = {0, 1, 2, 5, 4, 3, 6, 7, 8};
#define GLOW_FIRST 9
#define KEY_TALK 7 /* push-to-talk: F20 is sent in host mode too */

/* status colours from design.json */
static const rgb_t status_rgb[ST_COUNT] = {
    [ST_IDLE]  = {.r = 0xee, .g = 0xf2, .b = 0xf5},
    [ST_RUN]   = {.r = 0x3d, .g = 0x8b, .b = 0xff},
    [ST_DONE]  = {.r = 0x2f, .g = 0xbf, .b = 0x5b},
    [ST_NEEDS] = {.r = 0xff, .g = 0xb0, .b = 0x20},
    [ST_ERROR] = {.r = 0xff, .g = 0x4d, .b = 0x4f},
};
static const char *const status_name[ST_COUNT] = {"IDLE", "RUN", "DONE", "NEEDS", "ERROR"};
static const char status_letter[ST_COUNT]     = {'-', 'R', 'D', '?', '!'};

static const rgb_t white_rgb = {.r = 0xee, .g = 0xf2, .b = 0xf5};
#define GLOW_DEFAULT_R 0x7f
#define GLOW_DEFAULT_G 0xe3
#define GLOW_DEFAULT_B 0xff
#define GLOW_DEFAULT_BRI 70

/* brightness levels (0-255, applied to the colour) */
#define LVL_IDLE 22
#define LVL_IDLE_SEL 60
#define LVL_STATUS 110
#define LVL_CMD 22
#define LVL_PRESSED 150

/* rough current budget: sum of all channel values after scaling */
#define POWER_BUDGET (NUM_LEDS * 3 * 255 * 2 / 5)

/* ------------------------------------------------------------------------ */
/* State                                                                     */
/* ------------------------------------------------------------------------ */

static uint8_t  slot_status[NUM_SLOTS];
static bool     statuses_received;
static uint8_t  selected_slot;
static char     host_line[2][LINE_CHARS + 1];
static uint8_t  glow_r = GLOW_DEFAULT_R, glow_g = GLOW_DEFAULT_G, glow_b = GLOW_DEFAULT_B, glow_bri = GLOW_DEFAULT_BRI;

static bool     ever_pinged;
static uint32_t last_ping;
static bool     was_host_mode;

static uint32_t last_activity;

static bool     key_down[NUM_KEYS];
static bool     key_host[NUM_KEYS]; /* pressed while in host mode -> handled via HID */
static bool     key_hold_sent[NUM_KEYS];
static uint16_t key_press_time[NUM_KEYS];

/* per-LED fade: blend from a snapshot to the live target */
static rgb_t    led_last[NUM_LEDS];
static rgb_t    led_from[NUM_LEDS];
static uint32_t led_fade_start[NUM_LEDS];
static uint16_t led_fade_ms[NUM_LEDS];

/* ------------------------------------------------------------------------ */
/* Keymap: fallback keycodes (used only when no host has pinged for 5 s)     */
/* ------------------------------------------------------------------------ */

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_ortho_3x3(
        KC_F13, KC_F14, KC_F15,   /* agent 1-3 */
        KC_F16, KC_F17, KC_F18,   /* agent 4-6 */
        KC_F19, KC_F20, KC_ESC    /* approve, talk, stop */
    )
};
// clang-format on

/* ------------------------------------------------------------------------ */
/* Helpers                                                                   */
/* ------------------------------------------------------------------------ */

static bool host_mode(void) {
    return ever_pinged && timer_elapsed32(last_ping) < HOST_TIMEOUT_MS;
}

static void wake(void) {
    last_activity = timer_read32();
}

static void start_fade(uint8_t led, uint16_t ms) {
    led_from[led]       = led_last[led];
    led_fade_start[led] = timer_read32();
    led_fade_ms[led]    = ms;
}

static void set_status(uint8_t slot, uint8_t st, uint16_t fade_ms) {
    if (slot >= NUM_SLOTS) return;
    if (st >= ST_COUNT) st = ST_IDLE;
    if (slot_status[slot] == st) return;
    slot_status[slot] = st;
    start_fade(key_led[slot], fade_ms);
    wake();
}

static void set_glow(uint8_t r, uint8_t g, uint8_t b, uint8_t bri, uint16_t fade_ms) {
    if (r == glow_r && g == glow_g && b == glow_b && bri == glow_bri) return;
    glow_r   = r;
    glow_g   = g;
    glow_b   = b;
    glow_bri = bri;
    for (uint8_t i = GLOW_FIRST; i < NUM_LEDS; i++) start_fade(i, fade_ms);
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

/* sine wave 0..255 with the given period */
static uint8_t wave(uint32_t now, uint16_t period) {
    return sin8((uint8_t)(((now % period) * 256UL) / period));
}

static rgb_t scale_rgb(rgb_t c, uint8_t level) {
    rgb_t o = {.r = scale8(c.r, level), .g = scale8(c.g, level), .b = scale8(c.b, level)};
    return o;
}

static rgb_t blend_rgb(rgb_t a, rgb_t b, uint8_t t) {
    rgb_t o = {.r = lerp8by8(a.r, b.r, t), .g = lerp8by8(a.g, b.g, t), .b = lerp8by8(a.b, b.b, t)};
    return o;
}

/* ------------------------------------------------------------------------ */
/* Keys                                                                      */
/* ------------------------------------------------------------------------ */

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    uint8_t row = record->event.key.row;
    uint8_t col = record->event.key.col;
    if (row >= MATRIX_ROWS || col >= MATRIX_COLS) return true;
    uint8_t idx = row * MATRIX_COLS + col;

    wake();

    if (record->event.pressed) {
        key_down[idx] = true;
        if (host_mode()) {
            key_host[idx]       = true;
            key_hold_sent[idx]  = false;
            key_press_time[idx] = timer_read();
            return idx == KEY_TALK; /* Talk also always holds F20 */
        }
        key_host[idx] = false;
        return true; /* fallback: send the keymap keycode */
    }

    key_down[idx] = false;
    if (key_host[idx]) {
        key_host[idx] = false;
        if (!key_hold_sent[idx]) send_report(EVT_KEY, idx, 1); /* tap */
        return idx == KEY_TALK; /* release F20 */
    }
    return true; /* fallback release (also releases F20 for talk) */
}

/* ------------------------------------------------------------------------ */
/* Encoder                                                                   */
/* ------------------------------------------------------------------------ */

bool encoder_update_user(uint8_t index, bool clockwise) {
    wake();
    if (host_mode()) {
        selected_slot = clockwise ? (selected_slot + 1) % NUM_SLOTS : (selected_slot + NUM_SLOTS - 1) % NUM_SLOTS;
        send_report(EVT_ENCODER, clockwise ? 0x01 : 0xFF, selected_slot);
    } else {
        tap_code(clockwise ? KC_VOLU : KC_VOLD);
    }
    return false;
}

/* ------------------------------------------------------------------------ */
/* Raw HID                                                                   */
/* ------------------------------------------------------------------------ */

void raw_hid_receive(uint8_t *data, uint8_t length) {
    if (length < 1) return;

    switch (data[0]) {
        case CMD_SET_SLOT:
            if (length >= 3 && data[1] < NUM_SLOTS) {
                set_status(data[1], data[2], FADE_MS);
                statuses_received = true;
            }
            break;

        case CMD_SET_ALL:
            if (length >= 1 + NUM_SLOTS) {
                for (uint8_t i = 0; i < NUM_SLOTS; i++) set_status(i, data[1 + i], FADE_MS);
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
                if (strcmp(line, host_line[data[1]]) != 0) {
                    memcpy(host_line[data[1]], line, len + 1);
                    wake();
                }
            }
            break;

        case CMD_SET_GLOW:
            if (length >= 5) set_glow(data[1], data[2], data[3], data[4], FADE_MS);
            break;

        case CMD_PING:
            ever_pinged = true;
            last_ping   = timer_read32();
            send_report(CMD_PING, PROTOCOL_VERSION, selected_slot);
            break;

        case CMD_SET_SELECTED:
            if (length >= 2 && data[1] < NUM_SLOTS && data[1] != selected_slot) {
                selected_slot = data[1];
                wake();
            }
            break;

        default:
            break;
    }
}

/* ------------------------------------------------------------------------ */
/* Housekeeping: hold detection and host timeout                             */
/* ------------------------------------------------------------------------ */

void housekeeping_task_user(void) {
    for (uint8_t i = 0; i < NUM_KEYS; i++) {
        if (key_host[i] && !key_hold_sent[i] && timer_elapsed(key_press_time[i]) >= FROSTBITE_HOLD_MS) {
            key_hold_sent[i] = true;
            send_report(EVT_KEY, i, 2); /* hold, sent as soon as the threshold is crossed */
        }
    }

    bool hm = host_mode();
    if (was_host_mode && !hm) {
        /* host went away: fade everything back to idle and forget host text */
        for (uint8_t i = 0; i < NUM_SLOTS; i++) set_status(i, ST_IDLE, FALLBACK_FADE_MS);
        set_glow(GLOW_DEFAULT_R, GLOW_DEFAULT_G, GLOW_DEFAULT_B, GLOW_DEFAULT_BRI, FALLBACK_FADE_MS);
        host_line[0][0]   = '\0';
        host_line[1][0]   = '\0';
        statuses_received = false;
    }
    if (hm != was_host_mode) {
        /* selection highlight appears/disappears: fade it */
        for (uint8_t i = 0; i < NUM_SLOTS; i++) start_fade(key_led[i], FADE_MS);
    }
    was_host_mode = hm;
}

/* ------------------------------------------------------------------------ */
/* LEDs                                                                      */
/* ------------------------------------------------------------------------ */

static rgb_t agent_target(uint8_t slot, uint32_t now, bool hm) {
    uint8_t st    = hm ? slot_status[slot] : ST_IDLE;
    bool    sel   = hm && slot == selected_slot;
    uint8_t level = LVL_STATUS;

    switch (st) {
        case ST_IDLE:
            level = sel ? LVL_IDLE_SEL : LVL_IDLE;
            break;
        case ST_NEEDS: /* slow amber pulse */
            level = 30 + scale8(wave(now, 2400), 150);
            break;
        case ST_ERROR: /* blink red, 1 Hz */
            level = ((now / 500) & 1) ? 12 : 170;
            break;
        default:
            break;
    }

    if (sel) {
        /* selected slot: brighter, with a gentle breathe (x1.15 .. x1.6) */
        uint16_t gain = 294 + scale8(wave(now, 2000), 116);
        uint16_t l    = ((uint16_t)level * gain) >> 8;
        level         = l > 255 ? 255 : l;
    }
    if (key_down[slot] && level < LVL_PRESSED) level = LVL_PRESSED;

    return scale_rgb(status_rgb[st], level);
}

bool rgb_matrix_indicators_user(void) {
    uint32_t now = timer_read32();
    bool     hm  = host_mode();
    rgb_t    out[NUM_LEDS];

    for (uint8_t k = 0; k < NUM_KEYS; k++) {
        uint8_t led = key_led[k];
        if (k < NUM_SLOTS) {
            out[led] = agent_target(k, now, hm);
        } else {
            out[led] = scale_rgb(white_rgb, key_down[k] ? LVL_PRESSED : LVL_CMD);
        }
    }
    rgb_t glow = {.r = scale8(glow_r, glow_bri), .g = scale8(glow_g, glow_bri), .b = scale8(glow_b, glow_bri)};
    for (uint8_t i = GLOW_FIRST; i < NUM_LEDS; i++) out[i] = glow;

    /* fades */
    for (uint8_t i = 0; i < NUM_LEDS; i++) {
        if (led_fade_ms[i]) {
            uint32_t e = timer_elapsed32(led_fade_start[i]);
            if (e >= led_fade_ms[i]) {
                led_fade_ms[i] = 0;
            } else {
                out[i] = blend_rgb(led_from[i], out[i], (uint8_t)((e * 255UL) / led_fade_ms[i]));
            }
        }
        led_last[i] = out[i];
    }

    /* crude current limiter for USB power */
    uint32_t sum = 0;
    for (uint8_t i = 0; i < NUM_LEDS; i++) sum += out[i].r + out[i].g + out[i].b;
    uint8_t limit = 255;
    if (sum > POWER_BUDGET) limit = (uint8_t)((POWER_BUDGET * 255UL) / sum);

    for (uint8_t i = 0; i < NUM_LEDS; i++) {
        rgb_matrix_set_color(i, scale8(out[i].r, limit), scale8(out[i].g, limit), scale8(out[i].b, limit));
    }
    return false;
}

/* ------------------------------------------------------------------------ */
/* OLED                                                                      */
/* ------------------------------------------------------------------------ */

/* write exactly LINE_CHARS characters at the given row; shorter strings are
 * padded with spaces so leftovers from a longer previous line are blanked */
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
    static const uint8_t order[4]        = {ST_RUN, ST_NEEDS, ST_DONE, ST_ERROR};
    static const char *const labels[4]   = {"run", "wait", "done", "err"};
    uint8_t                  pos         = 0;
    dst[0]                               = '\0';
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
    if (timer_elapsed32(last_activity) > OLED_SLEEP_MS) {
        oled_off();
        return false;
    }
    oled_on();

    bool hm = host_mode();
    char line[32];

    /* line 1 */
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

    /* line 2 */
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

    /* row 2: dotted divider */
    oled_set_cursor(0, 2);
    oled_write_P(PSTR("                     "), false);
    for (uint8_t x = 0; x < 126; x += 3) oled_write_pixel(x, 19, true);

    /* row 3: slot strip "1- 2R 3D 4? 5! 6-  HID", selected slot inverted */
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

/* ------------------------------------------------------------------------ */
/* Init / power                                                              */
/* ------------------------------------------------------------------------ */

void keyboard_post_init_user(void) {
    /* Solid colour at value 0 is just a black canvas: rgb_matrix_indicators_user
     * paints every LED itself. Not written to EEPROM. */
    rgb_matrix_enable_noeeprom();
    rgb_matrix_mode_noeeprom(RGB_MATRIX_SOLID_COLOR);
    rgb_matrix_sethsv_noeeprom(0, 0, 0);
    wake();
}

void suspend_power_down_user(void) {
    oled_off();
}
