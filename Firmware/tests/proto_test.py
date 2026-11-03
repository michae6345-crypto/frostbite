# Real host encode/decode and Daemon against the real keymap.c in the harness. Usage: proto_test.py <harness binary>
# Run inside the host project: uv run --project host python Firmware/tests/proto_test.py <harness>
import subprocess, sys, json, re, time
from frostbite_host import device as D
from frostbite_host.daemon import Daemon
from frostbite_host.state import Board
from frostbite_host.actions import Actions
h=subprocess.Popen([sys.argv[1],'proto'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
def cmd(line):
    h.stdin.write(line+'\n'); h.stdin.flush()
    reps=[]
    while True:
        l=h.stdout.readline().rstrip('\n')
        if l.startswith('R '): reps.append(bytes.fromhex(l[2:]))
        else: 
            p=l[2:].split('|'); 
            return reps,dict(st=[int(x) for x in p[0].split()],sel=int(p[1]),l0=p[2],l1=p[3],glow=tuple(int(x) for x in p[4].split()),hm=int(p[5]),oled=int(p[6]))
def host(msg): return cmd('H '+D.encode(msg).hex())
ok=0;bad=0
def check(name,cond,extra=''):
    global ok,bad
    if cond: ok+=1; print('PASS',name)
    else: bad+=1; print('FAIL',name,extra)
# reports must be exactly 32 bytes
for m in [D.SetSlot(5,D.Status.ERROR),D.SetAll(tuple(D.Status(i%5) for i in range(6))),D.OledLine(1,'x'*40),D.SetGlow(1,2,3,4),D.Ping(),D.SetSelected(5)]:
    e=D.encode(m); assert len(e)==32; print(type(m).__name__, e[:9].hex(' '))
r,s=host(D.Ping()); check('PING reply decodes', len(r)==1 and D.decode_device(r[0])==D.PingReply(1,0), r)
check('PING raw bytes', r[0][:3]==bytes([5,1,0]) and r[0][3:]==bytes(29))
r,s=host(D.SetSlot(3,D.Status.NEEDS)); check('SET_SLOT', s['st'][3]==3)
r,s=host(D.SetAll((D.Status.RUN,D.Status.DONE,D.Status.NEEDS,D.Status.ERROR,D.Status.IDLE,D.Status.RUN))); check('SET_ALL', s['st']==[1,2,3,4,0,1],s)
r,s=host(D.OledLine(0,'hello world')); check('OLED_LINE 0', s['l0']=='hello world',s)
r,s=host(D.OledLine(1,'A'*21)); check('OLED_LINE 21 chars', s['l1']=='A'*21,s)
r,s=host(D.OledLine(1,'é→…'+chr(0x1f600))); print('  to_ascii ->',repr(s['l1']))
r,s=host(D.OledLine(1,'')); check('OLED_LINE empty clears', s['l1']=='',s)
r,s=host(D.SetGlow(10,20,30,40)); check('SET_GLOW', s['glow']==(10,20,30,40),s)
r,s=host(D.SetSelected(4)); check('SET_SELECTED', s['sel']==4,s)
r,s=host(D.Ping()); check('PING selected echoed', D.decode_device(r[0])==D.PingReply(1,4))
# keys, every index, tap
for row in range(3):
    for col in range(3):
        cmd('T 10'); host(D.Ping())
        cmd(f'K {row} {col} 1'); cmd('T 50'); r,_=cmd(f'K {row} {col} 0')
        m=D.decode_device(r[-1]); check(f'KEY tap {row},{col}', m==D.KeyEvent(row*3+col,D.TAP) and r[-1][3:]==bytes(29),m)
host(D.Ping()); cmd('K 2 1 1'); r,_=cmd('T 450'); check('KEY hold talk', D.decode_device(r[-1])==D.KeyEvent(7,D.HOLD),r); r,_=cmd('K 2 1 0'); check('no tap after hold', not r,r)
r,s=cmd('E 1'); check('ENCODER cw', D.decode_device(r[-1])==D.EncoderEvent(1,5) and r[-1][1]==1,r)
r,s=cmd('E 0'); check('ENCODER ccw', D.decode_device(r[-1])==D.EncoderEvent(-1,4) and r[-1][1]==0xFF,r)
print('--- scenario: host stall/sleep > 5 s with USB left open (no "disconnected" event)')
sent=[]
now=[1000.0]
dm=Daemon(Board(),Actions(dry_run=True,out=lambda s:None),send=lambda m:(sent.append(m),host(m)),clock=lambda:now[0])
host(D.Ping())
dm.handle_device('connected')
dm.submit({'op':'update','key':'slot:1','name':'build','status':'run','source':'ctl'})
dm.handle(dm.q.get())
r,s=host(D.Ping()); print('  before gap: ',s['st'],s['l0'],'|',s['l1'],s['glow'],'hm',s['hm'])
_,s=cmd('T 6000'); print('  firmware after 6 s without PING:',s['st'],repr(s['l0']),s['glow'],'hm',s['hm'])
sent.clear(); now[0]+=6.5
r,s=host(D.Ping()); dm.handle_device(D.decode_device(r[0]) if r else None); dm.tick()
print('  daemon sent after PING resumed:',[D.describe(m) for m in sent]); r,s=cmd('T 100'); print('  firmware now:',s['st'],repr(s['l0']),repr(s['l1']),s['glow'],'hm',s['hm'],' board statuses:',[int(x) for x in dm.board.statuses()])
print('--- scenario: OLED burn-in timer with a running slot, selected, daemon tick 1 Hz, 15 min')
on=[]; changes=0
for sec in range(900):
    now[0]+=1; n0=len(sent); dm.tick(); changes+=len([m for m in sent[n0:] if isinstance(m,D.OledLine)])
    if sec%2==0: host(D.Ping())
    r,s=cmd('T 1000'); on.append(s['oled'])
print('  OLED_LINE changes sent in 15 min:',changes,' OLED off seconds:',on.count(0),' of',len(on))
print('--- control: same 15 min, no daemon text changes')
offafter=None
for sec in range(700):
    if sec%2==0: host(D.Ping())
    r,s=cmd('T 1000')
    if s['oled']==0 and offafter is None: offafter=sec
print('  OLED went off after',offafter,'s')
print('ok',ok,'bad',bad)
h.stdin.close()
sys.exit(1 if bad or not ok else 0)
