// Host harness: #includes the REAL keymap.c, links the REAL drivers/oled/oled_driver.c.
#include "stub_qmk.h"
#include "raw_hid.h"
#include <stdio.h>
#include <assert.h>
#include "i2c_master.h"
uint32_t g_now=1000;
#include KEYMAP_FILE
#include "glcdfont.c"
typedef struct {uint8_t b[32];} rep_t;
static rep_t reps[4096]; static int nreps; static int bad_len;
void raw_hid_send(uint8_t*d,uint8_t n){ if(n!=32) bad_len++; if(nreps<4096) memcpy(reps[nreps++].b,d,32);}
static uint16_t taps[64]; static int ntaps; void tap_code_delay(uint16_t k,uint16_t d){ (void)d; if(ntaps<64) taps[ntaps++]=k; }
matrix_row_t matrix_get_row(uint8_t r){(void)r;return 0;}
extern int seg_remap,com_scan; extern unsigned long i2c_tx,i2c_bytes,panel_blocks[16]; extern int disp_toggles; extern uint8_t gddram[]; void panel_reset(void);
extern OLED_BLOCK_TYPE oled_dirty; extern uint8_t oled_buffer[]; extern bool oled_active;
void oled_task(void);
#define FAIL(...) do{printf("FAIL "__VA_ARGS__);printf("\n");fails++;}while(0)
#define PASS(...) do{printf("PASS "__VA_ARGS__);printf("\n");}while(0)
static int fails;
static void loop1(void){ g_now++; housekeeping_task_user(); oled_task(); }
static void run(uint32_t ms){ for(uint32_t i=0;i<ms;i++) loop1(); }
static bool ev(uint8_t r,uint8_t c,bool p){keyrecord_t k; memset(&k,0,sizeof k); k.event.key.row=r;k.event.key.col=c;k.event.pressed=p; return process_record_user(0,&k);}
static void rx(uint8_t a,uint8_t b,uint8_t c,uint8_t d,uint8_t e){uint8_t p[32]={a,b,c,d,e};raw_hid_receive(p,32);}
static void ping(void){rx(5,0,0,0,0);}
static void glyphs(const uint8_t*mem,char miss,int row,char*o){ for(int c=0;c<21;c++){ const uint8_t*cell=&mem[row*128+c*6]; char ch=miss; for(int g=32;g<127;g++){ if(!memcmp(cell,&font[g*6],6)){ch=g;break;} uint8_t inv[6]; for(int k=0;k<6;k++)inv[k]=~font[g*6+k]; if(!memcmp(cell,inv,6)){ch=g;break;} } o[c]=ch;} o[21]=0; }
static void rowtext(int row,char*o){glyphs(oled_buffer,'~',row,o);}
static void paneltext(int row,char*o){glyphs(gddram,'#',row,o);}
static void panelreport(const char*tag){ char r[22],q[22]; printf("--- %s (# = bytes the panel holds that are not a glyph)\n",tag); for(int i=0;i<4;i++){rowtext(i,r);paneltext(i,q);int unsent=0,diff=0;for(int b=0;b<128;b++){if(gddram[i*128+b]==0xA5&&oled_buffer[i*128+b]!=0xA5)unsent++; if(gddram[i*128+b]!=oled_buffer[i*128+b])diff++;} printf("page%d buffer |%s| panel |%s| bytes differing=%d never-written=%d\n",i,r,q,diff,unsent);} printf("blocks sent:"); for(int i=0;i<16;i++)printf(" %lu",panel_blocks[i]); printf("\n"); }
static void stripwant(const char*sc,char*w,const uint8_t*st,const char*mode){ char*p=w; for(int i=0;i<6;i++){*p++='1'+i;*p++=sc[st[i]];*p++=' ';} strcpy(p,mode); }
static int cellbad(const uint8_t*mem,const char*w,int sel){ int bad=0; for(int i=0;i<21;i++){ bool inv=sel>=0&&i/3==sel&&i%3<2&&i<18; for(int k=0;k<6;k++){ uint8_t g=font[w[i]*6+k]; if(mem[3*128+i*6+k]!=(inv?(uint8_t)~g:g)) bad++; } } return bad; }
static void reset_all(void){ memset(slot_status,0,sizeof slot_status); statuses_received=0;selected_slot=0;memset(host_line,0,sizeof host_line);ever_pinged=0;last_ping=0;memset(key_host,0,sizeof key_host);memset(key_hold_sent,0,sizeof key_hold_sent);memset(key_press_time,0,sizeof key_press_time);nreps=0;ntaps=0;wake(); }

static void t_taphold(uint32_t start,const char*tag){
  g_now=start; reset_all(); ping(); nreps=0;
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
      char r0[22],r3[22]; paneltext(0,r0); paneltext(3,r3); printf("S %d %d %d %d %d %d|%d|%s|%s|%d|%d|%s|%s\n",slot_status[0],slot_status[1],slot_status[2],slot_status[3],slot_status[4],slot_status[5],selected_slot,host_line[0],host_line[1],host_mode(),(int)oled_active,r0,r3);
    }
    return 0;
  }
  panel_reset(); oled_init(OLED_ROTATION_0); keyboard_post_init_user();
  printf("constants: OLED_BLOCK_SIZE=%d rep=%d\n",(int)(512/16),REPORT_BYTES);

  { g_now=1000; run(3000); panelreport("3 s after boot, no host"); ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); selected_slot=2; run(1500); ping(); run(500); panelreport("host mode, statuses set"); }
  // tap/hold across 16-bit and 32-bit timer wrap
  t_taphold(5000,"plain");
  t_taphold(65536-200,"16-bit wrap");
  t_taphold(0xFFFFFFFFu-200,"32-bit wrap");

  // mode transitions
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
    // host lost during a hold
    g_now+=6000; housekeeping_task_user(); ping(); nreps=0; ev(1,1,true); g_now+=5100; housekeeping_task_user(); printf("key held across host loss: reports=%d (hold event still sent)\n",nreps); ev(1,1,false);
  }
  // fallback timing
  { reset_all(); g_now=20000; ping(); uint32_t t0=g_now; housekeeping_task_user(); rx(1,0,1,0,0); rx(3,0,3,'a','b');
    g_now=t0+4999; if(host_mode())PASS("host mode still on at +4999 ms"); else FAIL("hm4999");
    g_now=t0+5000; if(!host_mode())PASS("host mode off at +5000 ms"); else FAIL("hm5000");
    housekeeping_task_user();
    printf("after fallback: status0=%d line0='%s' statuses_received=%d\n",slot_status[0],host_line[0],statuses_received);
  }
  // encoder
  { reset_all(); g_now=30000; ping(); nreps=0; int seq[8],n=0; for(int i=0;i<7;i++){encoder_update_user(0,true);seq[n++]=selected_slot;}
    printf("cw sequence:"); for(int i=0;i<7;i++)printf(" %d",seq[i]); printf("\n");
    selected_slot=0; encoder_update_user(0,false); if(selected_slot==5&&reps[nreps-1].b[1]==0xFF&&reps[nreps-1].b[2]==5)PASS("ccw wraps 0->5, report FF 05"); else FAIL("ccw");
    g_now+=6000; ntaps=0; uint8_t s=selected_slot; encoder_update_user(0,true); encoder_update_user(0,false); if(ntaps==2&&taps[0]==KC_VOLU&&taps[1]==KC_VOLD&&selected_slot==s)PASS("fallback: VOLU/VOLD, slot unchanged"); else FAIL("enc fb");
  }
  // malformed reports and fuzz
  { reset_all(); g_now=40000; ping(); uint8_t p[32]; memset(p,'X',32); p[0]=3;p[1]=0;p[2]=255; raw_hid_receive(p,32); if(strlen(host_line[0])==21)PASS("OLED_LINE len=255 truncated to 21"); else FAIL("len255 %zu",strlen(host_line[0]));
    p[1]=2; raw_hid_receive(p,32); p[1]=255; raw_hid_receive(p,32); PASS("line=2/255 ignored (ASan clean)");
    p[0]=3;p[1]=1;p[2]=30; raw_hid_receive(p,5); if(strlen(host_line[1])==2)PASS("OLED_LINE clamps to the bytes received"); else FAIL("short length=5 len=30: host_line1 strlen=%zu, want 2",strlen(host_line[1]));
    rx(1,6,1,0,0); rx(1,255,1,0,0); rx(6,6,0,0,0); rx(6,255,0,0,0); rx(1,0,200,0,0); if(selected_slot<6&&slot_status[0]==0)PASS("slot>5 ignored, status>4 -> idle"); else FAIL("slot");
    raw_hid_receive(p,0); raw_hid_receive(p,1); raw_hid_receive(p,2);
    uint64_t s=88172645463325252ULL; unsigned long N=3000000; for(unsigned long i=0;i<N;i++){ s^=s<<13;s^=s>>7;s^=s<<17; uint8_t q[32]; uint64_t x=s; for(int j=0;j<32;j++){ if(j%8==0){s^=s<<13;s^=s>>7;s^=s<<17;x=s;} q[j]=x>>(8*(j%8)); } if(i%2)q[0]=q[0]%8; if(i%3==0)q[1]=q[1]%8; int len=(i%5==0)?(int)(s%33):32; raw_hid_receive(q,len);
      if(i%1024==0){ g_now+=7; loop1(); ev(q[3]%3,q[4]%3,q[5]&1); }
      for(int k=0;k<2;k++){ assert(strlen(host_line[k])<=21); } assert(selected_slot<6); for(int k=0;k<6;k++)assert(slot_status[k]<5);
    }
    PASS("fuzz %lu packets: ASan/UBSan clean, invariants hold",N); printf("bad raw_hid_send lengths: %d\n",bad_len);
  }
  // every summary fits the row
  { unsigned maxn=0,maxc=0; int over=0; for(int c=0;c<15625;c++){int x=c; for(int i=0;i<6;i++){slot_status[i]=x%5;x/=5;} char l[32]; build_summary(l,false); unsigned n=strlen(l); if(n>maxn)maxn=n; if(n>21){build_summary(l,true); unsigned m=strlen(l); if(m>maxc)maxc=m; if(m>21)over++;} }
    printf("summary: 15625 combos, longest normal=%u compact=%u, over 21 after compact=%d\n",maxn,maxc,over); if(!over)PASS("summary fits"); else FAIL("summary"); }
  // 0x04 was SET_GLOW. It is an unknown command now, ignored like every other one.
  { reset_all(); g_now=65000; ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); uint8_t pl[32]={3,1,2,'h','i'}; raw_hid_receive(pl,32); selected_slot=2; run(100); ping(); run(1); nreps=0;
    uint8_t st0[6],buf0[512]; char ln0[2][22]; memcpy(st0,slot_status,6); memcpy(ln0,host_line,sizeof ln0); memcpy(buf0,oled_buffer,512); uint32_t la0=last_activity,lp0=last_ping; int known[]={1,2,3,5,6}; int tried=0;
    for(int c=0;c<256;c++){ int skip=0; for(int k=0;k<5;k++) if(c==known[k]) skip=1; if(skip) continue; uint8_t fills[3]={0,0xFF,(uint8_t)c}; int lens[4]={1,2,5,32};
      for(int f=0;f<3;f++) for(int l=0;l<4;l++){ uint8_t q[32]; memset(q,fills[f],32); q[0]=c; raw_hid_receive(q,lens[l]); tried++; } }
    run(20); int same=!memcmp(st0,slot_status,6)&&!memcmp(ln0,host_line,sizeof ln0)&&!memcmp(buf0,oled_buffer,512)&&selected_slot==2&&la0==last_activity&&lp0==last_ping;
    printf("unknown commands: %d reports, %d replies\n",tried,nreps); if(same&&!nreps)PASS("0x04 and every other unknown command change nothing and send nothing"); else FAIL("unknown same=%d replies=%d",same,nreps); }
  // Status lives on the OLED only: every status of every slot, with the selected cell inverted and no other.
  { static const char sc[5]={'-','R','D','?','!'}; reset_all(); g_now=67000; ping(); run(1); unsigned wrong=0; char r[22],w[22];
    for(int c=0;c<15625;c++){ int x=c; for(int i=0;i<6;i++){slot_status[i]=x%5;x/=5;} for(int sel=0;sel<6;sel++){ selected_slot=sel; oled_task_user(); rowtext(3,r); stripwant(sc,w,slot_status,"HID"); if(strcmp(r,w)||cellbad(oled_buffer,w,sel)) wrong++; } }
    printf("strip: 15625 status sets x 6 selections, wrong=%u\n",wrong); if(!wrong)PASS("strip shows every slot's status, selected cell inverted"); else FAIL("strip wrong=%u",wrong);
    reset_all(); g_now=68000; ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); uint8_t st[6]={1,3,2,4,0,1}; int bad=0; for(int sel=0;sel<6;sel++){ rx(6,sel,0,0,0); run(50); paneltext(3,r); stripwant(sc,w,st,"HID"); if(strcmp(r,w)||cellbad(gddram,w,sel)) bad++; }
    if(!bad)PASS("SET_SELECTED moves the inverted cell on the panel"); else FAIL("sel panel bad=%d",bad);
    ping(); nreps=0; rx(6,5,0,0,0); encoder_update_user(0,true); run(50); paneltext(3,r); if(selected_slot==0&&!cellbad(gddram,w,0))PASS("encoder moves the inverted cell on the panel, 5 wraps to 0"); else FAIL("enc panel sel=%d",selected_slot);
    g_now+=6000; run(50); paneltext(3,r); uint8_t idle[6]={0}; stripwant(sc,w,idle,"KBD"); if(!strcmp(r,w)&&!cellbad(gddram,w,-1))PASS("fallback strip: all idle, KBD, nothing inverted"); else FAIL("fb strip |%s|",r); }
  // OLED traffic and dirty blocks while idle
  { reset_all(); g_now=70000; run(2000); unsigned long b0=i2c_bytes,t0=i2c_tx; uint16_t dmask=0; for(int i=0;i<1000;i++){loop1(); dmask|=oled_dirty;} printf("idle KBD screen: %lu I2C bytes, %lu transactions in 1000 loops (=1000 ms of sim); residual dirty mask seen=0x%04x\n",i2c_bytes-b0,i2c_tx-t0,dmask);
    ping(); run(1500); ping(); run(1); b0=i2c_bytes; t0=i2c_tx; for(int i=0;i<1000;i++){loop1();} printf("idle HID screen: %lu I2C bytes in 1000 loops\n",i2c_bytes-b0);
    char r[22]; for(int i=0;i<4;i++){rowtext(i,r);printf("row%d |%s|\n",i,r);} }
  // OLED sleep timeline
  { reset_all(); g_now=80000; run(10); wake(); uint32_t t0=g_now; disp_toggles=0; run(600000-5); if(oled_active)PASS("OLED on at 599995 ms"); else FAIL("early off");
    int togg0=disp_toggles; run(30); printf("after timeout: oled_active=%d display toggles in 30 ms=%d elapsed=%u dirty=0x%x\n",oled_active,disp_toggles-togg0,(unsigned)(g_now-t0),oled_dirty);
    run(1000); if(!oled_active)PASS("stays off"); else FAIL("did not stay off");
    ping(); run(2100); ping(); run(100); if(!oled_active)PASS("repeat PING does not wake"); else FAIL("ping woke");
    rx(1,0,0,0,0); run(10); if(!oled_active)PASS("no-change SET_SLOT does not wake"); else FAIL("nochange woke");
    rx(1,0,1,0,0); run(10); if(oled_active)PASS("changed SET_SLOT wakes"); else FAIL("no wake");
    run(610000); printf("off again=%d\n",!oled_active); ev(0,0,true); ev(0,0,false); run(10); if(oled_active)PASS("key wakes"); else FAIL("key no wake");
    // USB resume wakes once, then the normal timer runs; PING never counts
    { reset_all(); g_now=800000; ping(); uint8_t a[32]={2,3,0,0,0,0,0}; raw_hid_receive(a,32); run(10); wake();
      run(610000); if(!oled_active)PASS("before sleep: OLED already asleep"); else FAIL("not asleep");
      oled_off(); /* QMK does this itself on suspend */ g_now+=3600000; housekeeping_task_user(); run(50);
      if(!oled_active)PASS("no resume event yet: stays dark"); else FAIL("lit without resume");
      suspend_wakeup_init_user(); run(50); printf("resume after 60 min sleep: oled_active=%d\n",oled_active);
      if(oled_active)PASS("USB resume wakes the OLED"); else FAIL("resume did not wake");
      ping(); run(50); char r[22]; paneltext(3,r); if(!strncmp(r,"1? 2- 3- 4- 5- 6- HID",21))PASS("waiting prompt is on the panel after resume"); else FAIL("resume panel |%s|",r);
      /* 15 min of PINGs, same-value SET_ALL and changing text after that one resume */
      uint32_t t0=last_activity; uint32_t first_off=0; int off_ms=0, relit=0; bool prev=true;
      for(uint32_t t=0;t<900000;t++){ loop1(); if(t%2000==0){ ping(); raw_hid_receive(a,32); } if(t%1000==0){ char q[32]={3,1,21}; memset(q+3,' ',21); q[3]='0'+(t/1000)%10; raw_hid_receive((uint8_t*)q,32); }
        if(!oled_active){ off_ms++; if(!first_off)first_off=g_now-t0; } if(oled_active&&!prev&&first_off)relit++; prev=oled_active; }
      printf("after resume: last_activity moved=%d, first off %u ms after resume, off for %d s of 900, relit=%d\n",last_activity!=t0,first_off,off_ms/1000,relit);
      if(last_activity==t0)PASS("PING, SET_ALL and OLED_LINE do not extend the resume wake"); else FAIL("activity moved");
      if(first_off>600000&&first_off<=600100&&!relit)PASS("sleeps 10 min after resume with PINGs running, stays off"); else FAIL("first_off=%u relit=%d",first_off,relit);
      /* second resume: wakes once more; a short sleep restarts the timer once */
      suspend_wakeup_init_user(); run(20); if(oled_active)PASS("each resume wakes once"); else FAIL("second resume"); t0=last_activity; run(300000); ping(); if(oled_active&&last_activity==t0)PASS("still on the same timer"); else FAIL("timer moved");
    }
  }
  { reset_all(); g_now=90000; ping(); g_now+=6000; housekeeping_task_user(); uint32_t lp=last_ping; g_now=lp+0xFFFFFFFFu; bool h1=host_mode(); g_now=lp+1; bool h2=host_mode(); if(!h1&&!h2)PASS("host mode stays off across timer wrap"); else FAIL("wrap: elapsed=2^32-1 host_mode=%d; elapsed wrapped to 1 host_mode=%d, want 0 0",h1,h2); }
  // OLED strip and divider reach the panel. verify/fbverify/checks.py matches the PASS F1 lines by text.
  { reset_all(); g_now=200000; run(3000);
    int bad=0; for(int b=0;b<512;b++) if(gddram[b]!=oled_buffer[b]) bad++;
    char r[22]; panelreport("F1 KBD screen"); if(!bad)PASS("F1 KBD: panel matches buffer on all 4 pages"); else FAIL("F1 KBD diff=%d",bad);
    unsigned long b0=i2c_bytes; run(1000); if(i2c_bytes==b0)PASS("F1 idle screen: 0 I2C bytes in 1000 loops"); else FAIL("F1 idle i2c %lu",i2c_bytes-b0);
    ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); selected_slot=2; run(1500); ping(); run(500);
    bad=0; for(int b=0;b<512;b++) if(gddram[b]!=oled_buffer[b]) bad++; panelreport("F1 HID screen"); paneltext(3,r);
    if(!bad&&!strncmp(r,"1R 2? 3D 4! 5- 6R HID",21))PASS("F1 HID: slot strip and HID reach the panel"); else FAIL("F1 HID diff=%d |%s|",bad,r);
    int dots=0; for(int x=0;x<128;x++) if(gddram[2*128+x]&0x08) dots++; printf("divider dots on panel=%d\n",dots); if(dots==42)PASS("F1 divider all 42 dots on panel"); else FAIL("F1 dots");
    rx(3,0,21,'A','A'); run(50); uint8_t pl[32]={3,0,3,'a','b','c'}; raw_hid_receive(pl,32); run(50); paneltext(0,r); if(!strcmp(r,"abc                  "))PASS("shorter OLED_LINE blanks the rest on the panel"); else FAIL("short |%s|",r);
  }
  { // PING gap with no reconnect, then SET_ALL in place
    reset_all(); g_now=300000; ping(); uint8_t a[32]={2,1,3,2,4,0,1}; raw_hid_receive(a,32); uint8_t pl[32]={3,1,2,'h','i'}; raw_hid_receive(pl,32); run(1000); ping(); run(500);
    uint32_t t0=last_activity; run(5200+1600);
    char r[22]; paneltext(3,r); printf("gap: host_mode=%d stored=[%d %d %d %d %d %d] strip |%s|\n",host_mode(),slot_status[0],slot_status[1],slot_status[2],slot_status[3],slot_status[4],slot_status[5],r);
    if(!strncmp(r,"1- 2- 3- 4- 5- 6- KBD",21))PASS("gap: strip shows idle/KBD"); else FAIL("gap render");
    ping(); raw_hid_receive(a,32); uint32_t la=last_activity; run(1000); ping(); run(500); paneltext(3,r);
    if(la==t0)PASS("same-value SET_ALL is not OLED activity"); else FAIL("SET_ALL woke");
    if(!strncmp(r,"1R 2? 3D 4! 5- 6R HID",21))PASS("strip restored in place, no reconnect"); else FAIL("strip |%s|",r);
    if(!strcmp(host_line[1],"hi"))PASS("gap keeps OLED text, so the daemon's _sent stays true"); else FAIL("retained");
  }
  { // 15 min of daemon traffic, no key or status change
    reset_all(); g_now=400000; ping(); uint8_t a[32]={2,1,0,0,0,0,0}; raw_hid_receive(a,32); wake(); uint32_t t0=g_now; int offs=0,changes=0; uint32_t first_off=0;
    for(uint32_t t=0;t<900000;t++){ loop1();
      if(t%2000==0){ ping(); raw_hid_receive(a,32); }
      if(t%1000==0){ char q[32]={3,0,21}; memset(q+3,' ',21); q[3]='0'+(t/60000)%10; q[4]='0'+(t/1000)%10; raw_hid_receive((uint8_t*)q,32); changes++; rx(4,t/1000%256,2,3,40); rx(6,(t/1000)%6,0,0,0);}
      if(!oled_active){ offs++; if(!first_off)first_off=t; } }
    printf("15 min: text/select updates and unknown 0x04=%d, off for %d s of 900, first off at %u s\n",changes,offs/1000,first_off/1000);
    if(first_off&&first_off<=600100&&offs>=299000)PASS("sleep fires at 10 min under daemon traffic and stays off"); else FAIL("first_off=%u offs=%d",first_off,offs);
    a[1]=2; raw_hid_receive(a,32); run(20); if(oled_active)PASS("real status change wakes"); else FAIL("status no wake");
    run(610000); ping(); if(!oled_active)PASS("asleep again"); else FAIL("no resleep"); encoder_update_user(0,true); run(20); if(oled_active)PASS("encoder wakes"); else FAIL("enc no wake");
    run(610000); ev(0,0,true); ev(0,0,false); run(20); if(oled_active)PASS("key wakes after daemon traffic"); else FAIL("key no wake");
  }
  { // host mode and OLED sleep across timer wrap
    reset_all(); g_now=500000; ping(); run(6000); uint32_t lp=last_ping; g_now=lp-1; run(5); bool h=host_mode(); if(!h)PASS("no false host mode after wrap"); else FAIL("hm after wrap");
    wake(); run(610000); int off=!oled_active; g_now=last_activity-2; run(40); if(off&&!oled_active)PASS("OLED stays dark across wrap"); else FAIL("oled off=%d active=%d",off,oled_active);
  }
  { // real frostbite.c oled_init_kb
    printf("oled init: seg_remap=0x%02x com_scan=0x%02x (flipped is 0xa0 0xc0)\n",seg_remap,com_scan); if(seg_remap==0xA0&&com_scan==0xC0)PASS("init sends the flipped command set"); else FAIL("oled init");
  }
  printf("fails=%d\n",fails); return fails!=0;
}
