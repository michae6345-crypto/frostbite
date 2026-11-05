/* Compiles the real Firmware/.../keymap.c unmodified and drives it from stdin.
   R <hex>     raw_hid_receive(data, 32)      K <idx> <0|1> key up/down in current mode
   E <0|1>     encoder ccw/cw                 T <ms>        advance clock, run housekeeping
   D           dump state as one line */
#include "../../../Firmware/qmk/keyboards/frostbite/keymaps/default/keymap.c"
#include <stdlib.h>
uint32_t fake_now=1000; char oled_rows[4][64]; int oled_row,oled_col;
void oled_set_cursor(uint8_t c,uint8_t r){oled_row=r;oled_col=c;}
void oled_write(const char*s,bool inv){while(*s&&oled_col<63){oled_rows[oled_row][oled_col++]=*s++;}oled_rows[oled_row][oled_col]=0;}
void raw_hid_send(uint8_t*d,uint8_t n){printf("SEND ");for(int i=0;i<n;i++)printf("%02x",d[i]);printf("\n");}
static void dump(void){oled_task_user();
 printf("STATE sel=%d status=",selected_slot);for(int i=0;i<NUM_SLOTS;i++)printf("%d",slot_status[i]);
 printf(" line0=[%s] line1=[%s] oled0=[%s] oled1=[%s] oled3=[%s] host=%d\n",host_line[0],host_line[1],oled_rows[0],oled_rows[1],oled_rows[3],host_mode());}
int main(void){char b[256];uint8_t d[32];setvbuf(stdout,0,_IOLBF,0);keyboard_post_init_user();
 while(fgets(b,sizeof b,stdin)){switch(b[0]){
  case 'R':{memset(d,0,32);for(int i=0;i<32;i++){unsigned v;if(sscanf(b+2+i*2,"%2x",&v)!=1)break;d[i]=v;}raw_hid_receive(d,32);break;}
  case 'K':{int i,p;sscanf(b+2,"%d %d",&i,&p);keyrecord_t r;r.event.key.row=i/3;r.event.key.col=i%3;r.event.pressed=p;printf("KEYRET %d\n",process_record_user(0,&r));break;}
  case 'E':{int c;sscanf(b+2,"%d",&c);encoder_update_user(0,c);break;}
  case 'T':{int m;sscanf(b+2,"%d",&m);fake_now+=m;housekeeping_task_user();break;}
  case 'D':dump();break;}}
 return 0;}
