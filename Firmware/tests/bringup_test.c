// Desk test for the bring-up keymap: the REAL keymaps/bringup/keymap.c, the REAL OLED driver, the panel model.
#include "stub_qmk.h"
#include <stdio.h>
#include "i2c_master.h"
uint32_t g_now=1000;
#include KEYMAP_FILE
#include "glcdfont.c"
matrix_row_t matrix_get_row(uint8_t r){(void)r;return 0;}
extern unsigned long i2c_bytes; extern uint8_t gddram[]; void panel_reset(void);
extern uint8_t oled_buffer[];
void oled_task(void);
#define FAIL(...) do{printf("FAIL "__VA_ARGS__);printf("\n");fails++;}while(0)
#define PASS(...) do{printf("PASS "__VA_ARGS__);printf("\n");}while(0)
static int fails;
static void run(uint32_t ms){ for(uint32_t i=0;i<ms;i++){ g_now++; oled_task(); } }
static bool key(uint8_t r,uint8_t c,bool p){keyrecord_t k; memset(&k,0,sizeof k); k.event.key.row=r;k.event.key.col=c;k.event.pressed=p; return process_record_user(0,&k);}
static void row(int n,char*o){ for(int c=0;c<21;c++){ char ch='#'; for(int g=32;g<127;g++) if(!memcmp(&gddram[n*128+c*6],&font[g*6],6)){ch=g;break;} o[c]=ch; } o[21]=0; }
static bool shows(int n,const char*want){ char r[22],w[22]; snprintf(w,sizeof w,"%-21s",want); row(n,r); if(strcmp(r,w)){printf("row %d |%s| want |%s|\n",n,r,w);return false;} return true; }
int main(void){
  static const char *const names[9]={"r0 c0 Agent 1","r0 c1 Agent 2","r0 c2 Agent 3","r1 c0 Agent 4","r1 c1 Agent 5","r1 c2 Agent 6","r2 c0 Approve","r2 c1 Talk","r2 c2 Stop"};
  static const uint16_t codes[9]={KC_F13,KC_F14,KC_F15,KC_F16,KC_F17,KC_F18,KC_F19,KC_F20,KC_ESC};
  panel_reset(); oled_init(OLED_ROTATION_0); keyboard_post_init_user();
  run(100); int off=0; for(int b=0;b<512;b++) if(gddram[b]!=0xFF) off++;
  if(!off)PASS("bringup: every pixel lit after boot"); else FAIL("bringup: %d panel bytes not lit",off);
  run(2850); off=0; for(int b=0;b<512;b++) if(gddram[b]!=0xFF) off++;
  if(!off)PASS("bringup: pixels stay lit until 3 s"); else FAIL("bringup: lit test ended early, %d bytes",off);
  run(150); int lit=0; for(int p=0;p<4;p++) for(int x=126;x<128;x++) if(gddram[p*128+x]) lit++;
  if(!lit&&!memcmp(gddram,oled_buffer,512))PASS("bringup: screen cleared to the last column after the pixel test"); else FAIL("bringup: lit=%d",lit);
  if(shows(0,"BRINGUP  keys 0/9")&&shows(1,"seen .........")&&shows(2,"key: -")&&shows(3,"knob: turn it"))PASS("bringup: start screen on the panel"); else FAIL("bringup: start screen");
  unsigned long b0=i2c_bytes; run(1000); if(i2c_bytes==b0)PASS("bringup: 0 I2C bytes while idle"); else FAIL("bringup: idle i2c %lu",i2c_bytes-b0);
  int bad=0; char seen[10]="........."; for(int i=0;i<9;i++){ if(!key(i/3,i%3,true)||!key(i/3,i%3,false)) bad++; if(keymaps[0][i/3][i%3]!=codes[i]) bad++; run(40); seen[i]='1'+i; char w[22];
    snprintf(w,sizeof w,"BRINGUP  keys %d/9",i+1); if(!shows(0,w)) bad++; snprintf(w,sizeof w,"seen %s",seen); if(!shows(1,w)) bad++; snprintf(w,sizeof w,"key: %s",names[i]); if(!shows(2,w)) bad++; }
  if(!bad)PASS("bringup: all 9 keys named and counted, fallback keycodes pass through"); else FAIL("bringup: keys bad=%d",bad);
  key(0,0,true); key(0,0,false); key(0,0,true); key(0,0,false); run(40); if(shows(0,"BRINGUP  keys 9/9"))PASS("bringup: a repeat press does not count twice"); else FAIL("bringup: repeat");
  key(2,1,true); key(1,0,true); run(40); if(shows(2,"key: r1 c0 Agent 4"))PASS("bringup: release does not change the last key"); else FAIL("bringup: last key"); key(1,0,false); key(2,1,false); run(40); if(!shows(2,"key: r1 c0 Agent 4")) FAIL("bringup: last key after release");
  bool r=encoder_update_user(0,true); run(40); if(!r&&shows(3,"knob: 1 CW"))PASS("bringup: clockwise reads CW, no volume"); else FAIL("bringup: cw");
  r=encoder_update_user(0,false); r|=encoder_update_user(0,false); run(40); if(!r&&shows(3,"knob: -1 CCW"))PASS("bringup: counter-clockwise reads CCW, count goes negative"); else FAIL("bringup: ccw");
  printf("bringup fails=%d\n",fails); return fails!=0;
}
