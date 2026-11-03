/* Minimal stand-ins so the REAL keymap.c compiles on the laptop. Audit only. */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#define PROGMEM
#define PSTR(x) x
#define MATRIX_ROWS 3
#define MATRIX_COLS 3
#define LAYOUT_ortho_3x3(a,b,c,d,e,f,g,h,i) {{a,b,c},{d,e,f},{g,h,i}}
enum { KC_F13=1,KC_F14,KC_F15,KC_F16,KC_F17,KC_F18,KC_F19,KC_F20,KC_ESC,KC_VOLU,KC_VOLD };
typedef struct { uint8_t r,g,b; } rgb_t;
typedef struct { struct { struct { uint8_t row,col; } key; bool pressed; } event; } keyrecord_t;
typedef enum { OLED_ROTATION_180 } oled_rotation_t;
extern uint32_t fake_now;
static inline uint32_t timer_read32(void){return fake_now;}
static inline uint16_t timer_read(void){return (uint16_t)fake_now;}
static inline uint32_t timer_elapsed32(uint32_t t){return fake_now-t;}
static inline uint16_t timer_elapsed(uint16_t t){return (uint16_t)((uint16_t)fake_now-t);}
extern char oled_rows[4][64]; extern int oled_row, oled_col;
void oled_set_cursor(uint8_t c,uint8_t r); void oled_write(const char*s,bool inv);
static inline void oled_write_P(const char*s,bool inv){oled_write(s,inv);}
static inline void oled_write_char(char c,bool inv){char b[2]={c,0};oled_write(b,inv);}
static inline void oled_write_pixel(uint8_t x,uint8_t y,bool on){}
static inline void oled_on(void){} static inline void oled_off(void){}
static inline void tap_code(uint16_t k){printf("TAP %d\n",k);}
static inline void rgb_matrix_set_color(int i,uint8_t r,uint8_t g,uint8_t b){}
static inline void rgb_matrix_enable_noeeprom(void){} static inline void rgb_matrix_mode_noeeprom(int m){}
static inline void rgb_matrix_sethsv_noeeprom(int h,int s,int v){}
#define RGB_MATRIX_SOLID_COLOR 1
