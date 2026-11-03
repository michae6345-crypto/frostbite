// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include_next <mcuconf.h>

/* OLED lives on the RP2040's I2C1 block (GP6/GP7). */
#undef RP_I2C_USE_I2C1
#define RP_I2C_USE_I2C1 TRUE
