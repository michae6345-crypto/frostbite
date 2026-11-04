// Copyright 2026 Frostbite contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include_next <mcuconf.h>

/* GP6/GP7 are on the RP2040's I2C1 block. */
#undef RP_I2C_USE_I2C1
#define RP_I2C_USE_I2C1 TRUE
