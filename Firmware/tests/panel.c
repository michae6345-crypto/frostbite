// SSD1306 GDDRAM model behind the I2C stub. Power-on GDDRAM is filled with 0xA5 as a marker for "never written".
#include <stdint.h>
#include <string.h>
#include "i2c_master.h"
int seg_remap=-1,com_scan=-1;
uint8_t gddram[512]; unsigned long i2c_tx,i2c_bytes,panel_blocks[16]; int disp_toggles; static int disp_on=-1;
static int c0,c1=127,p0,p1=3,col,page;
void panel_reset(void){memset(gddram,0xA5,512);}
void i2c_init(void){}
i2c_status_t i2c_transmit(uint8_t a,const uint8_t*d,uint16_t n,uint16_t t){(void)a;(void)t;i2c_tx++;i2c_bytes+=n+1;
  if(n==2&&(d[1]==0xAE||d[1]==0xAF)){int v=d[1]==0xAF; if(v!=disp_on){disp_on=v;disp_toggles++;}}
  if(n>1&&(d[1]==0xA0||d[1]==0xA1)){seg_remap=d[1];com_scan=d[2];}
  if(n==7&&d[1]==0x21&&d[4]==0x22){c0=d[2];c1=d[3];p0=d[5];p1=d[6];col=c0;page=p0;}
  return 0;}
i2c_status_t i2c_write_register(uint8_t a,uint8_t r,const uint8_t*d,uint16_t n,uint16_t t){(void)a;(void)r;(void)t;i2c_tx++;i2c_bytes+=n+2;
  panel_blocks[(page*128+col)/32]++;
  for(int i=0;i<n;i++){ gddram[page*128+col]=d[i]; if(++col>c1){col=c0; if(++page>p1)page=p0;} } return 0;}
