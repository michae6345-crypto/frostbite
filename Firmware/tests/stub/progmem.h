#pragma once
#include <string.h>
#define PROGMEM
#define PSTR(x) x
#define memcpy_P memcpy
#define pgm_read_byte(p) (*(const uint8_t*)(p))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
