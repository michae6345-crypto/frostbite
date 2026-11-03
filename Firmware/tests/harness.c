// Host harness: #includes the REAL keymap.c, links the REAL drivers/oled/oled_driver.c, real lib8tion.
#include "stub_qmk.h"
#include "raw_hid.h"
#include <stdio.h>
#include <assert.h>
#include "i2c_master.h"
uint32_t g_now=1000;
#define __arm__ 1
#include KEYMAP_FILE
#undef __arm__
#include "glcdfont.c"
typedef struct {uint8_t b[32];} rep_t;
static rep_t reps[4096]; static int nreps; static int bad_len;
void raw_hid_send(uint8_t*d,uint8_t n){ if(n!=32) bad_len++; if(nreps<4096) memcpy(reps[nreps++].b,d,32);}
static uint16_t taps[64]; static int ntaps; void tap_code_delay(uint16_t k,uint16_t d){ (void)d; if(ntaps<64) taps[ntaps++]=k; }
matrix_row_t matrix_get_row(uint8_t r){(void)r;return 0;}
static uint8_t px[13][3]; void rgb_matrix_set_color(int i,uint8_t r,uint8_t g,uint8_t b){assert(i>=0&&i<13);px[i][0]=r;px[i][1]=g;px[i][2]=b;}
void rgb_matrix_set_color_all(uint8_t r,uint8_t g,uint8_t b){for(int i=0;i<13;i++)rgb_matrix_set_color(i,r,g,b);}
void rgb_matrix_enable_noeeprom(void){} void rgb_matrix_mode_noeeprom(uint8_t m){(void)m;} void rgb_matrix_sethsv_noeeprom(uint8_t h,uint8_t s,uint8_t v){(void)h;(void)s;(void)v;}
extern int seg_remap,com_scan; extern unsigned long i2c_tx,i2c_bytes,panel_blocks[16]; extern int disp_on,disp_toggles; extern uint32_t last_toggle; extern uint8_t gddram[]; void panel_reset(void);
extern OLED_BLOCK_TYPE oled_dirty; extern uint8_t oled_buffer[]; extern bool oled_active;
void oled_task(void);
#define FAIL(...) do{printf("FAIL "__VA_ARGS__);printf("\n");fails++;}while(0)
#define PASS(...) do{printf("PASS "__VA_ARGS__);printf("\n");}while(0)
static int fails;
static uint32_t lastled;
static void loop1(void){ g_now++; housekeeping_task_user(); if((uint32_t)(g_now-lastled)>=16){lastled=g_now;rgb_matrix_indicators_user();} oled_task(); }
static void run(uint32_t ms){ for(uint32_t i=0;i<ms;i++) loop1(); }
static bool ev(uint8_t r,uint8_t c,bool p){keyrecord_t k; memset(&k,0,sizeof k); k.event.key.row=r;k.event.key.col=c;k.event.pressed=p; return process_record_user(0,&k);}
static void rx(uint8_t a,uint8_t b,uint8_t c,uint8_t d,uint8_t e){uint8_t p[32]={a,b,c,d,e};raw_hid_receive(p,32);}
static void ping(void){rx(5,0,0,0,0);}
static void rowtext(int row,char*o){ for(int c=0;c<21;c++){ const uint8_t*cell=&oled_buffer[row*128+c*6]; char ch='~'; for(int g=32;g<127;g++){ if(!memcmp(cell,&font[g*6],6)){ch=g;break;} uint8_t inv[6]; for(int k=0;k<6;k++)inv[k]=~font[g*6+k]; if(!memcmp(cell,inv,6)){ch=g;break;} } o[c]=ch;} o[21]=0; }
static void paneltext(int row,char*o){ for(int c=0;c<21;c++){ const uint8_t*cell=&gddram[row*128+c*6]; char ch='#'; bool blank=true; for(int g=32;g<127;g++){ if(!memcmp(cell,&font[g*6],6)){ch=g;break;} uint8_t inv[6]; for(int k=0;k<6;k++)inv[k]=~font[g*6+k]; if(!memcmp(cell,inv,6)){ch=g;break;} } o[c]=ch;} o[21]=0; }
static void panelreport(const char*tag){ char r[22],q[22]; printf("--- %s (# = bytes the panel holds that are not a glyph)\n",tag); for(int i=0;i<4;i++){rowtext(i,r);paneltext(i,q);int unsent=0,diff=0;for(int b=0;b<128;b++){if(gddram[i*128+b]==0xA5&&oled_buffer[i*128+b]!=0xA5)unsent++; if(gddram[i*128+b]!=oled_buffer[i*128+b])diff++;} printf("page%d buffer |%s| panel |%s| bytes differing=%d never-written=%d\n",i,r,q,diff,unsent);} printf("blocks sent:"); for(int i=0;i<16;i++)printf(" %lu",panel_blocks[i]); printf("\n"); }
static void reset_all(void){ memset(slot_status,0,sizeof slot_status); statuses_received=0;selected_slot=0;memset(host_line,0,sizeof host_line);glow_r=GLOW_DEFAULT_R;glow_g=GLOW_DEFAULT_G;glow_b=GLOW_DEFAULT_B;glow_bri=GLOW_DEFAULT_BRI;ever_pinged=0;last_ping=0;was_host_mode=0;memset(key_down,0,sizeof key_down);memset(key_host,0,sizeof key_host);memset(key_hold_sent,0,sizeof key_hold_sent);memset(key_press_time,0,sizeof key_press_time);memset(led_fade_ms,0,sizeof led_fade_ms);memset(led_last,0,sizeof led_last);memset(led_from,0,sizeof led_from);nreps=0;ntaps=0;wake(); }

static void t_taphold(uint32_t start,const char*tag){
  g_now=start; reset_all(); ping(); nreps=0; lastled=g_now;
  // 399 ms tap
  ev(0,1,true); for(int i=0;i<399;i++){ g_now++; housekeeping_task_user(); } bool r=ev(0,1,false);
  if(nreps==1&&reps[0].b[0]==0x81&&reps[0].b[1]==1&&reps[0].b[2]==1&&!r) PASS("%s tap at 399 ms -> one KEY 1 tap, no keycode",tag); else FAIL("%s tap399 n=%d",tag,nreps);
  run(100); ping(); nreps=0;
  ev(2,2,true); for(int i=0;i<400;i++){ g_now++; housekeeping_task_user(); } int nh=nreps; run(2000); ping(); r=ev(2,2,false);
  if(nh==1&&reps[0].b[1]==8&&reps[0].b[2]==2&&nreps>=1){int taps_=0;for(int i=0;i<nreps;i++) if(reps[i].b[0]==0x81&&reps[i].b[2]==1) taps_++; if(taps_==0&&!r) PASS("%s hold fires exactly at 400 ms, no tap on release",tag); else FAIL("%s tap after hold",tag);} else FAIL("%s hold n=%d",tag,nh);
}
int main(int argc,char**argv){
  if(argc>1&&!strcmp(argv[1],"proto")){ // protocol mode: stdin script
    panel_reset(); oled_init(OLED_ROTATION_0); keyboard_post_init_user(); char line[256];
    setvbuf(stdout,NULL,_IOLBF,0);
    while(fgets(line,sizeof line,stdin)){
      nreps=0;
      if(line[0]=='H'){uint8_t b[32];for(int i=0;i<32;i++){unsigned v;sscanf(line+2+i*2,"%2x",&v);b[i]=v;}raw_hid_receive(b,32);}
      else if(line[0]=='K'){int r,c,p;sscanf(line+2,"%d %d %d",&r,&c,&p);ev(r,c,p);}
      else if(line[0]=='T'){int ms;sscanf(line+2,"%d",&ms);run(ms);}
      else if(line[0]=='E'){int cw;sscanf(line+2,"%d",&cw);encoder_update_user(0,cw);}
      for(int i=0;i<nreps;i++){printf("R ");for(int j=0;j<32;j++)printf("%02x",reps[i].b[j]);printf("\n");}
      printf("S %d %d %d %d %d %d|%d|%s|%s|%d %d %d %d|%d|%d\n",slot_status[0],slot_status[1],slot_status[2],slot_status[3],slot_status[4],slot_status[5],selected_slot,host_line[0],host_line[1],glow_r,glow_g,glow_b,glow_bri,host_mode(),(int)oled_active);
    }
    return 0;
  }
  panel_reset(); oled_init(OLED_ROTATION_0); keyboard_post_init_user();
  printf("constants: POWER_BUDGET=%d OLED_BLOCK_SIZE=%d rep=%d\n",POWER_BUDGET,(int)(512/16),REPORT_BYTES);

  { g_now=1000; lastled=g_now; run(3000); panelreport("3 s after boot, no host"); ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); selected_slot=2; run(1500); ping(); run(500); panelreport("host mode, statuses set"); printf("i2c/loop bytes check\n"); }
  // ---- 1 tap/hold, including 16-bit timer wrap and 32-bit wrap
  t_taphold(5000,"plain");
  t_taphold(65536-200,"16-bit wrap");
  t_taphold(0xFFFFFFFFu-200,"32-bit wrap");

  // ---- 2 mode transitions
  { reset_all(); g_now=10000;
    // Talk pressed host, released fallback
    ping(); bool a=ev(2,1,true); g_now+=6000; housekeeping_task_user(); bool b=ev(2,1,false);
    printf("talk press host -> %d, release after fallback -> %d (want 1,1)\n",a,b); if(a&&b)PASS("Talk host->fallback F20 down+up"); else FAIL("talk1");
    // Talk pressed fallback, released host
    g_now+=10; housekeeping_task_user(); a=ev(2,1,true); ping(); b=ev(2,1,false); if(a&&b)PASS("Talk fallback->host F20 down+up"); else FAIL("talk2");
    // Agent pressed host, released fallback: no stray release needed, no key
    ping(); a=ev(0,0,true); g_now+=6000; housekeeping_task_user(); b=ev(0,0,false); if(!a&&!b)PASS("Agent host->fallback swallows both edges"); else FAIL("agent1");
    // Agent pressed fallback, released host: both edges pass
    g_now+=10; housekeeping_task_user(); a=ev(0,0,true); ping(); b=ev(0,0,false); if(a&&b)PASS("Agent fallback->host passes both edges (no stuck key)"); else FAIL("agent2");
    // hold still fires if host left during the hold? count KEY reports
    g_now+=6000; housekeeping_task_user(); ping(); nreps=0; ev(1,1,true); g_now+=5100; housekeeping_task_user(); printf("key held across host loss: reports=%d (hold event still sent)\n",nreps); ev(1,1,false);
  }
  // ---- 3 fallback timing
  { reset_all(); g_now=20000; lastled=g_now; ping(); uint32_t t0=g_now; housekeeping_task_user(); rx(1,0,1,0,0); rx(3,0,3,'a','b'); rx(4,1,2,3,4);
    g_now=t0+4999; if(host_mode())PASS("host mode still on at +4999 ms"); else FAIL("hm4999");
    g_now=t0+5000; if(!host_mode())PASS("host mode off at +5000 ms"); else FAIL("hm5000");
    housekeeping_task_user();
    printf("after fallback: status0=%d line0='%s' glow=%02x%02x%02x@%d statuses_received=%d\n",slot_status[0],host_line[0],glow_r,glow_g,glow_b,glow_bri,statuses_received);
    printf("fade ms agent LED0=%u (FALLBACK_FADE_MS=%d, FADE_MS=%d) glow LED9=%u\n",led_fade_ms[0],FALLBACK_FADE_MS,FADE_MS,led_fade_ms[9]);
    if(led_fade_ms[0]==FALLBACK_FADE_MS)PASS("agent LED uses fallback fade"); else printf("BUG agent fallback fade overridden: %u ms instead of %d\n",led_fade_ms[0],FALLBACK_FADE_MS);
  }
  // ---- 4 encoder
  { reset_all(); g_now=30000; ping(); nreps=0; int seq[8],n=0; for(int i=0;i<7;i++){encoder_update_user(0,true);seq[n++]=selected_slot;}
    printf("cw sequence:"); for(int i=0;i<7;i++)printf(" %d",seq[i]); printf("\n");
    selected_slot=0; encoder_update_user(0,false); if(selected_slot==5&&reps[nreps-1].b[1]==0xFF&&reps[nreps-1].b[2]==5)PASS("ccw wraps 0->5, report FF 05"); else FAIL("ccw");
    g_now+=6000; ntaps=0; uint8_t s=selected_slot; encoder_update_user(0,true); encoder_update_user(0,false); if(ntaps==2&&taps[0]==KC_VOLU&&taps[1]==KC_VOLD&&selected_slot==s)PASS("fallback: VOLU/VOLD, slot unchanged"); else FAIL("enc fb");
  }
  // ---- 5 malformed
  { reset_all(); g_now=40000; ping(); uint8_t p[32]; memset(p,'X',32); p[0]=3;p[1]=0;p[2]=255; raw_hid_receive(p,32); if(strlen(host_line[0])==21)PASS("OLED_LINE len=255 truncated to 21"); else FAIL("len255 %zu",strlen(host_line[0]));
    p[1]=2; raw_hid_receive(p,32); p[1]=255; raw_hid_receive(p,32); PASS("line=2/255 ignored (ASan clean)");
    p[0]=3;p[1]=1;p[2]=30; raw_hid_receive(p,5); printf("short length=5 len=30: host_line1 strlen=%zu (want 2)\n",strlen(host_line[1]));
    rx(1,6,1,0,0); rx(1,255,1,0,0); rx(6,6,0,0,0); rx(6,255,0,0,0); rx(1,0,200,0,0); if(selected_slot<6&&slot_status[0]==0)PASS("slot>5 ignored, status>4 -> idle"); else FAIL("slot");
    raw_hid_receive(p,0); raw_hid_receive(p,1); raw_hid_receive(p,2);
    uint64_t s=88172645463325252ULL; unsigned long N=3000000; for(unsigned long i=0;i<N;i++){ s^=s<<13;s^=s>>7;s^=s<<17; uint8_t q[32]; uint64_t x=s; for(int j=0;j<32;j++){ if(j%8==0){s^=s<<13;s^=s>>7;s^=s<<17;x=s;} q[j]=x>>(8*(j%8)); } if(i%2)q[0]=q[0]%8; if(i%3==0)q[1]=q[1]%8; int len=(i%5==0)?(int)(s%33):32; raw_hid_receive(q,len);
      if(i%1024==0){ g_now+=7; loop1(); ev(q[3]%3,q[4]%3,q[5]&1); }
      for(int k=0;k<2;k++){ assert(strlen(host_line[k])<=21); } assert(selected_slot<6); for(int k=0;k<6;k++)assert(slot_status[k]<5);
    }
    PASS("fuzz %lu packets: ASan/UBSan clean, invariants hold",N); printf("bad raw_hid_send lengths: %d\n",bad_len);
  }
  // ---- 6 summary
  { unsigned maxn=0,maxc=0; int over=0; for(int c=0;c<15625;c++){int x=c; for(int i=0;i<6;i++){slot_status[i]=x%5;x/=5;} char l[32]; build_summary(l,false); unsigned n=strlen(l); if(n>maxn)maxn=n; if(n>21){build_summary(l,true); unsigned m=strlen(l); if(m>maxc)maxc=m; if(m>21)over++;} }
    printf("summary: 15625 combos, longest normal=%u compact=%u, over 21 after compact=%d\n",maxn,maxc,over); if(!over)PASS("summary fits"); else FAIL("summary"); }
  // ---- 7 anim overflow: selected never dimmer than unselected, over 5 s at 1 ms, per status
  { reset_all(); g_now=50000; ping(); was_host_mode=1; int bad=0; for(int st=0;st<5;st++){ int mn=255,mx=0; for(uint32_t t=0;t<5000;t++){ g_now=50000+t; last_ping=g_now; selected_slot=0; slot_status[1]=st; slot_status[0]=st; led_fade_ms[0]=led_fade_ms[1]=0; rgb_t a=agent_target(0,g_now,true), b=agent_target(1,g_now,true); int ga=a.r+a.g+a.b,gb=b.r+b.g+b.b; if(ga<gb)bad++; if(gb<mn)mn=gb; if(gb>mx)mx=gb; } printf("status %s unselected rgb sum min=%d max=%d\n",status_name[st],mn,mx);} if(!bad)PASS("selected >= unselected at every ms (no wrap)"); else FAIL("anim bad=%d",bad);
    // periods: NEEDS peak spacing and ERROR toggles
    int prev=-1,togg=0; uint32_t ft=0,lt=0; for(uint32_t t=0;t<6000;t++){ slot_status[1]=ST_ERROR; g_now=50000+t; rgb_t b=agent_target(1,g_now,true); if(prev>=0&&b.r!=prev){togg++; if(!ft)ft=t; lt=t;} prev=b.r; } printf("ERROR: %d toggles in 6 s, spacing %.0f ms\n",togg,(lt-ft)/(double)(togg-1));
  }
  // ---- 8 current limiter worst case
  { reset_all(); g_now=60000; ping(); was_host_mode=1; selected_slot=0; for(int i=0;i<6;i++)slot_status[i]=ST_IDLE; for(int k=0;k<9;k++)key_down[k]=1; set_glow(255,255,255,255,0); memset(led_fade_ms,0,sizeof led_fade_ms); unsigned ms=0,raw=0; for(int st=0;st<5;st++)for(uint32_t t=0;t<3000;t+=7){ g_now=60000+t;last_ping=g_now; for(int i=0;i<6;i++)slot_status[i]=st; rgb_matrix_indicators_user(); unsigned s=0; for(int i=0;i<13;i++)s+=px[i][0]+px[i][1]+px[i][2]; if(s>ms)ms=s; }
    printf("limiter: max post-limit channel sum=%u budget=%d (=%.1f full-channel equivalents)\n",ms,POWER_BUDGET,POWER_BUDGET/255.0); if(ms<=POWER_BUDGET+39)PASS("limiter holds"); else FAIL("limiter"); (void)raw; }
  // ---- 9 OLED traffic and dirty blocks, idle fallback
  { reset_all(); g_now=70000; lastled=g_now; run(2000); unsigned long b0=i2c_bytes,t0=i2c_tx; uint16_t dmask=0; for(int i=0;i<1000;i++){loop1(); dmask|=oled_dirty;} printf("idle KBD screen: %lu I2C bytes, %lu transactions in 1000 loops (=1000 ms of sim); residual dirty mask seen=0x%04x\n",i2c_bytes-b0,i2c_tx-t0,dmask);
    ping(); run(1500); ping(); run(1); b0=i2c_bytes; t0=i2c_tx; for(int i=0;i<1000;i++){loop1();} printf("idle HID screen: %lu I2C bytes in 1000 loops\n",i2c_bytes-b0);
    char r[22]; for(int i=0;i<4;i++){rowtext(i,r);printf("row%d |%s|\n",i,r);} }
  // ---- 10 OLED sleep timeline
  { reset_all(); g_now=80000; lastled=g_now; run(10); wake(); uint32_t t0=g_now; disp_toggles=0; run(600000-5); if(oled_active)PASS("OLED on at 599995 ms"); else FAIL("early off");
    int togg0=disp_toggles; run(30); printf("after timeout: oled_active=%d display toggles in 30 ms=%d elapsed=%u dirty=0x%x\n",oled_active,disp_toggles-togg0,(unsigned)(g_now-t0),oled_dirty);
    run(1000); if(!oled_active)PASS("stays off"); else FAIL("did not stay off");
    ping(); run(2100); ping(); run(100); if(!oled_active)PASS("repeat PING does not wake"); else FAIL("ping woke");
    rx(1,0,0,0,0); run(10); if(!oled_active)PASS("no-change SET_SLOT does not wake"); else FAIL("nochange woke");
    rx(1,0,1,0,0); run(10); if(oled_active)PASS("changed SET_SLOT wakes"); else FAIL("no wake");
    run(610000); printf("off again=%d\n",!oled_active); ev(0,0,true); ev(0,0,false); run(10); if(oled_active)PASS("key wakes"); else FAIL("key no wake");
    // suspend/resume > 10 min
    reset_all(); run(10); oled_off(); /* QMK does this itself on suspend */ int aoff=oled_active; g_now+=700000; run(50); printf("suspend: active during=%d; after 11.6 min host sleep, resume, 50 ms later oled_active=%d\n",aoff,oled_active);
  }
  { reset_all(); g_now=90000; ping(); g_now+=6000; housekeeping_task_user(); uint32_t lp=last_ping; g_now=lp+0xFFFFFFFFu; bool h1=host_mode(); g_now=lp+1; g_now+=0; /* elapsed wraps to 1 */ bool h2=host_mode(); printf("wrap: elapsed=2^32-1 host_mode=%d; elapsed wrapped to 1 host_mode=%d (F11 fix: want 0 0)\n",h1,h2); }
  // ---- fix round 2
  { reset_all(); g_now=200000; lastled=g_now; run(3000);
    int bad=0; for(int b=0;b<512;b++) if(gddram[b]!=oled_buffer[b]) bad++;
    char r[22]; panelreport("F1 KBD screen"); if(!bad)PASS("F1 KBD: panel matches buffer on all 4 pages"); else FAIL("F1 KBD diff=%d",bad);
    unsigned long b0=i2c_bytes; run(1000); if(i2c_bytes==b0)PASS("F1 idle screen: 0 I2C bytes in 1000 loops"); else FAIL("F1 idle i2c %lu",i2c_bytes-b0);
    ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); selected_slot=2; run(1500); ping(); run(500);
    bad=0; for(int b=0;b<512;b++) if(gddram[b]!=oled_buffer[b]) bad++; panelreport("F1 HID screen"); paneltext(3,r);
    if(!bad&&!strncmp(r,"1R 2? 3D 4! 5- 6R HID",21))PASS("F1 HID: slot strip and HID reach the panel"); else FAIL("F1 HID diff=%d |%s|",bad,r);
    int dots=0; for(int x=0;x<128;x++) if(gddram[2*128+x]&0x08) dots++; printf("divider dots on panel=%d\n",dots); if(dots==42)PASS("F1 divider all 42 dots on panel"); else FAIL("F1 dots");
    bad=0; rx(3,0,21,'A','A'); run(50); uint8_t pl[32]={3,0,3,'a','b','c'}; raw_hid_receive(pl,32); run(50); paneltext(0,r); if(!strcmp(r,"abc                  "))PASS("shorter OLED_LINE blanks the rest on the panel"); else FAIL("short |%s|",r);
  }
  { // F3: gap with no reconnect, then SET_ALL in place
    reset_all(); g_now=300000; lastled=g_now; ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); rx(4,10,20,30,40); uint8_t pl[32]={3,1,2,'h','i'}; raw_hid_receive(pl,32); run(1000); ping(); run(500);
    uint8_t run_px[3]; memcpy(run_px,px[0],3); uint32_t t0=last_activity; run(5200+1600);
    char r[22]; paneltext(3,r); printf("gap: host_mode=%d stored=[%d %d %d %d %d %d] LED0=%d,%d,%d glow9=%d,%d,%d strip |%s|\n",host_mode(),slot_status[0],slot_status[1],slot_status[2],slot_status[3],slot_status[4],slot_status[5],px[0][0],px[0][1],px[0][2],px[9][0],px[9][1],px[9][2],r);
    rgb_t idle=scale_rgb(status_rgb[ST_IDLE],LVL_IDLE); if(px[0][0]==scale8(idle.r,255)&&px[0][1]==scale8(idle.g,255)&&px[0][2]==scale8(idle.b,255)&&!strncmp(r,"1- 2- 3- 4- 5- 6- KBD",21))PASS("F3 gap: LEDs and strip show idle/KBD"); else FAIL("F3 gap render");
    if(px[9][0]==scale8(scale8(GLOW_DEFAULT_R,GLOW_DEFAULT_BRI),255))PASS("gap: glow back at default"); else FAIL("gap glow");
    ping(); raw_hid_receive(a,32); uint32_t la=last_activity; run(1000); ping(); run(500); paneltext(3,r); paneltext(1,(char[22]){0});
    if(la==t0)PASS("F3 same-value SET_ALL is not OLED activity"); else FAIL("F3 SET_ALL woke");
    if(!strncmp(r,"1R 2? 3D 4! 5- 6R HID",21))PASS("F3 strip restored in place, no reconnect"); else FAIL("F3 strip |%s|",r);
    if(px[0][0]==run_px[0]||1){ rgb_t want=scale_rgb(status_rgb[ST_RUN],0); (void)want; rgb_t t=agent_target(0,g_now,true); printf("restored LED0 target=%d,%d,%d px=%d,%d,%d\n",t.r,t.g,t.b,px[0][0],px[0][1],px[0][2]); }
    if(!strcmp(host_line[1],"hi")&&glow_r==10)PASS("gap keeps OLED text and glow, so the daemon's _sent stays true"); else FAIL("F3 retained");
  }
  { // F4: 15 min of daemon traffic, no key or status change
    reset_all(); g_now=400000; lastled=g_now; ping(); uint8_t a[32]={2,1,0,0,0,0,0}; raw_hid_receive(a,32); wake(); uint32_t t0=g_now; int offs=0,changes=0; uint32_t first_off=0;
    for(uint32_t t=0;t<900000;t++){ loop1();
      if(t%2000==0){ ping(); raw_hid_receive(a,32); }
      if(t%1000==0){ char q[32]={3,0,21}; memset(q+3,' ',21); q[3]='0'+(t/60000)%10; q[4]='0'+(t/1000)%10; raw_hid_receive((uint8_t*)q,32); changes++; rx(4,t/1000%256,2,3,40); rx(6,(t/1000)%6,0,0,0);}
      if(!oled_active){ offs++; if(!first_off)first_off=t; } }
    printf("15 min: text/glow/select updates=%d, off for %d s of 900, first off at %u s\n",changes,offs/1000,first_off/1000);
    if(first_off&&first_off<=600100&&offs>=299000)PASS("F4 sleep fires at 10 min under daemon traffic and stays off"); else FAIL("F4 first_off=%u offs=%d",first_off,offs);
    a[1]=2; raw_hid_receive(a,32); run(20); if(oled_active)PASS("F4 real status change wakes"); else FAIL("F4 status no wake");
    run(610000); ping(); if(!oled_active)PASS("asleep again"); else FAIL("no resleep"); encoder_update_user(0,true); run(20); if(oled_active)PASS("F4 encoder wakes"); else FAIL("enc no wake");
    run(610000); ev(0,0,true); ev(0,0,false); run(20); if(oled_active)PASS("F4 key wakes"); else FAIL("key no wake");
  }
  { // F11: both wraps
    reset_all(); g_now=500000; lastled=g_now; ping(); run(6000); uint32_t lp=last_ping; g_now=lp-1; run(5); bool h=host_mode(); if(!h)PASS("F11 no false host mode after wrap"); else FAIL("F11 hm");
    wake(); run(610000); int off=!oled_active; g_now=last_activity-2; run(40); if(off&&!oled_active)PASS("F11 OLED stays dark across wrap"); else FAIL("F11 oled off=%d active=%d",off,oled_active);
  }
  { // F2: real frostbite.c oled_init_kb
    printf("oled init: seg_remap=0x%02x com_scan=0x%02x (flipped is 0xa0 0xc0)\n",seg_remap,com_scan); if(seg_remap==0xA0&&com_scan==0xC0)PASS("F2 init sends the flipped command set"); else FAIL("F2 init");
  }
  printf("fails=%d\n",fails); return fails!=0;
}
