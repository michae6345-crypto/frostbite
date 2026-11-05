// Copyright 2026 Michael Tarekegn
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_TIMEOUT 500U

// oled on i2c1, d4 = gp6 sda, d5 = gp7 scl
#define I2C_DRIVER I2CD1
#define I2C1_SDA_PIN GP6
#define I2C1_SCL_PIN GP7
#define OLED_DISPLAY_128X32
#define OLED_DISPLAY_ADDRESS 0x3C
// keymap.c does its own sleep timer
#define OLED_TIMEOUT 0
#define OLED_BRIGHTNESS 160

#define FROSTBITE_HOLD_MS 400

// comment this out if the oled is upside down
#define FROSTBITE_OLED_FLIP

// from seeed's xiao board header, the xosc can be slow to start
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
