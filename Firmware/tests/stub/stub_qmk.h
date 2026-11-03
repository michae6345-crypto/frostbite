#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include "progmem.h"
#include "timer.h"
#include "oled_driver.h"
#define MATRIX_ROWS 3
#define MATRIX_COLS 3
typedef struct {uint8_t r,g,b;} rgb_t;
typedef struct {uint8_t col,row;} keypos_t;
typedef struct {keypos_t key; bool pressed;} keyevent_t;
typedef struct {keyevent_t event;} keyrecord_t;
enum {KC_F13=0x68,KC_F14,KC_F15,KC_F16,KC_F17,KC_F18,KC_F19,KC_F20,KC_ESC=0x29,KC_VOLU=0x80,KC_VOLD=0x81};
#define LAYOUT_ortho_3x3(a,b,c,d,e,f,g,h,i) {{a,b,c},{d,e,f},{g,h,i}}
#define RGB_MATRIX_SOLID_COLOR 1
void tap_code(uint16_t k);
void rgb_matrix_set_color(int i,uint8_t r,uint8_t g,uint8_t b);
void rgb_matrix_set_color_all(uint8_t r,uint8_t g,uint8_t b);
void rgb_matrix_enable_noeeprom(void);
void rgb_matrix_mode_noeeprom(uint8_t m);
void rgb_matrix_sethsv_noeeprom(uint8_t h,uint8_t s,uint8_t v);

void tap_code_delay(uint16_t code, uint16_t delay);
typedef uint16_t matrix_row_t;
matrix_row_t matrix_get_row(uint8_t row);
