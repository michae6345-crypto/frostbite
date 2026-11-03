#pragma once
#include <stdint.h>
extern uint32_t g_now;
static inline uint32_t timer_read32(void){return g_now;}
static inline uint16_t timer_read(void){return (uint16_t)g_now;}
static inline uint16_t timer_elapsed(uint16_t l){return (uint16_t)((uint16_t)g_now-l);}
static inline uint32_t timer_elapsed32(uint32_t l){return (uint32_t)(g_now-l);}
#define timer_expired32(c,f) ((uint32_t)((f)-(c))>=0x80000000UL)
