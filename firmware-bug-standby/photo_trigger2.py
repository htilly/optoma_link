import socket,time,sys
H="172.16.205.161"
def log(m):
    t=time.time(); print(f"[{time.strftime('%H:%M:%S',time.localtime(t))}.{int(t%1*1000):03d}] {m}",flush=True)
def conn(t=4):
    s=socket.create_connection((H,23),timeout=t); s.settimeout(t); return s
def q(s,c,t=3):
    s.settimeout(t); t0=time.time()
    try:
        s.sendall(c.encode()+b"\r"); r=s.recv(256)
    except Exception as e: r=b"NOREPLY/"+type(e).__name__.encode()
    return r,time.time()-t0
log("armed - burst starts in 30 s"); time.sleep(30)
try:
    s=conn(3); p,_=q(s,"~00124 1"); s.close()
except Exception as e: p=("ERR "+str(e)).encode()
log(f"GATE power={p!r}")
if p!=b"OK1\r": log("gate not OK1 -> sending nothing"); sys.exit(0)
log("BURST START")
s=conn(); trunc=None
for i in range(1,201):
    r,d=q(s,"~0087 3")
    if i%10==0: log(f"  #{i} {r!r} {d:.2f}s")
    ok=r.startswith(b"Ok172") and r.endswith(b"\r")
    if not ok and trunc is None:
        trunc=i; log(f"FIRST ABNORMAL (truncated/none) at #{i}: {r!r}  -> keep querying until service stops answering")
    elif not ok:
        log(f"  #{i} {r!r}")
    if trunc is not None:
        if r.startswith(b"NOREPLY") or i-trunc>=12:
            log(f"STOP at #{i}: {r!r}  <-- on-screen text should show NOW (1-2 s)"); break
else: log("no failure in 200 queries")
try: s.close()
except: pass
time.sleep(2)
for k in range(3):
    try:
        s2=conn(3); p,_=q(s2,"~00124 1"); s2.close(); log(f"after: power={p!r}")
    except Exception as e: log(f"after: {e}")
    time.sleep(3)
log("DONE")
