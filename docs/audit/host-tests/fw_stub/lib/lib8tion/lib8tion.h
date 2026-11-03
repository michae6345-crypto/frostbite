#pragma once
#include <stdint.h>
static inline uint8_t scale8(uint8_t a,uint8_t b){return ((uint16_t)a*(uint16_t)(b+1))>>8;}
static inline uint8_t sin8(uint8_t x){return x;}
static inline uint8_t lerp8by8(uint8_t a,uint8_t b,uint8_t t){return a+(((int)b-(int)a)*t)/255;}
