// Round 2 firmware front end. Reuses Firmware/tests/harness.c unchanged (real keymap.c, real QMK OLED driver,
// SSD1306 GDDRAM model) and adds a line protocol with panel text, LED values, display power and the keycodes
// that reach USB. Commands: H <hex> | K r c p | T ms | E cw | Z ms (USB suspend then resume) | W (state only)
#define main harness_orig_main
#include HARNESS_FILE
#undef main
static uint32_t down_mask; static int stray_release;
static void jstr(const char*k,const char*v){ printf("\"%s\":\"",k); for(;*v;v++){ if(*v=='"'||*v=='\\')putchar('\\'); putchar(*v);} printf("\","); }
static void state(void){
  char r[22]; printf("S {\"st\":[%d,%d,%d,%d,%d,%d],\"sel\":%d,",slot_status[0],slot_status[1],slot_status[2],slot_status[3],slot_status[4],slot_status[5],selected_slot);
  jstr("l0",host_line[0]); jstr("l1",host_line[1]);
  for(int i=0;i<4;i++){ char k[8]; snprintf(k,8,"p%d",i); paneltext(i,r); jstr(k,r); }
  printf("\"glow\":[%d,%d,%d,%d],\"hm\":%d,\"oled\":%d,\"disp\":%d,\"asleep\":%d,\"down\":%u,\"stray\":%d,\"now\":%u,\"led\":[",glow_r,glow_g,glow_b,glow_bri,host_mode(),(int)oled_active,disp_on,(int)oled_asleep,down_mask,stray_release,g_now);
  for(int i=0;i<13;i++) printf("%s[%d,%d,%d]",i?",":"",px[i][0],px[i][1],px[i][2]);
  printf("]}\n");
}
int main(void){
  panel_reset(); oled_init(OLED_ROTATION_0); keyboard_post_init_user(); char line[256]; setvbuf(stdout,NULL,_IOLBF,0); lastled=g_now;
  while(fgets(line,sizeof line,stdin)){
    nreps=0;
    if(line[0]=='H'){uint8_t b[32];for(int i=0;i<32;i++){unsigned v;sscanf(line+2+i*2,"%2x",&v);b[i]=v;}raw_hid_receive(b,32);}
    else if(line[0]=='K'){int r,c,p;sscanf(line+2,"%d %d %d",&r,&c,&p); bool pass=ev(r,c,p); uint32_t bit=1u<<(r*3+c);
      if(pass&&p) down_mask|=bit; else if(pass&&!p){ if(!(down_mask&bit)) stray_release++; down_mask&=~bit; }
      printf("P %d\n",(int)pass);}
    else if(line[0]=='T'){int ms;sscanf(line+2,"%d",&ms);run(ms);}
    else if(line[0]=='E'){int cw;sscanf(line+2,"%d",&cw);encoder_update_user(0,cw);}
    else if(line[0]=='Z'){unsigned ms;sscanf(line+2,"%u",&ms); oled_off(); g_now+=ms; /* main loop is parked in protocol_pre_task */ }
    for(int i=0;i<nreps;i++){printf("R ");for(int j=0;j<32;j++)printf("%02x",reps[i].b[j]);printf("\n");}
    state();
  }
  return 0;
}
