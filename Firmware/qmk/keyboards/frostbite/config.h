// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

/* Double-tap the XIAO RESET button to enter the RP2040 UF2 bootloader. */
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_TIMEOUT 500U

/* OLED: 0.91" SSD1306 128x32 on I2C1 (XIAO D4 = GP6 SDA, D5 = GP7 SCL). */
#define I2C_DRIVER I2CD1
#define I2C1_SDA_PIN GP6
#define I2C1_SCL_PIN GP7
#define OLED_DISPLAY_128X32
#define OLED_DISPLAY_ADDRESS 0x3C
/* Burn-in timeout is handled in the keymap (wakes on HID too), so the
 * driver's own input-only timeout is disabled. */
#define OLED_TIMEOUT 0
#define OLED_BRIGHTNESS 160

/* Raw HID (QMK defaults are 0xFF60 / 0x61, stated here to match design.json). */
#define RAW_USAGE_PAGE 0xFF60
#define RAW_USAGE_ID 0x61

/* Hold-detection threshold for the Raw HID KEY event (tap vs hold). */
#define FROSTBITE_HOLD_MS 400

/* OLED rotated 180 degrees: the header sits at the right end of the module, and
 * reference Hackpads with this placement all flip it. Not yet confirmed on a
 * fitted Frostbite module. If the text is upside down, comment out this line. */
#define FROSTBITE_OLED_FLIP

/* Seeed's XIAO RP2040 board header sets this: "On some samples, the xosc can
 * take longer to stabilize than is usual" (pico-sdk seeed_xiao_rp2040.h). */
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
