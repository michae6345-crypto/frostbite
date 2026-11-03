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

/* Uncomment if the OLED text appears upside down (check with the ledtest build). */
// #define FROSTBITE_OLED_FLIP
