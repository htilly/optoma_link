import socket,time,sys
H="172.16.205.161"
def log(m):
    t=time.time(); print(f"[{time.strftime('%H:%M:%S',time.localtime(t))}.{int(t%1*1000):03d}] {m}",flush=True)
def conn(t=4):
    s=socket.create_connection((H,23),timeout=t); s.settimeout(t); return s
def q(s,c,t=3):
    s.settimeout(t); t0=time.time(); s.sendall(c.encode()+b"\r")
    try: r=s.recv(256)
    except Exception: r=b"NOREPLY"
    return r,time.time()-t0
def power():
    try:
        s=conn(3); r,_=q(s,"~00124 1",3); s.close(); return r
    except Exception as e: return ("ERR "+str(e)).encode()
def wait_recover(maxs=120):
    t0=time.time()
    while time.time()-t0<maxs:
        time.sleep(5); p=power(); log(f"  recover-check power={p!r} ({time.time()-t0:.0f}s)")
        if p==b"OK1\r":
            time.sleep(10); return time.time()-t0
    return None
log("GATE"); p=power(); log(f"power={p!r}")
if p!=b"OK1\r": log("gate not OK1 -> stop"); sys.exit(0)
for delay in [1.0,0.5,0.25,0.1,0.0]:
    log(f"=== PHASE delay={delay}s between queries, max 80 queries, one connection ===")
    s=conn(); bad=None; durs=[]
    for i in range(1,81):
        r,d=q(s,"~0087 3"); durs.append(d)
        ok=r.startswith(b"Ok172") and r.endswith(b"\r")
        if i%10==0 or not ok: log(f"  #{i:02d} {r!r} {d:.2f}s")
        if not ok: bad=i; break
        time.sleep(delay)
    try: s.close()
    except: pass
    log(f"PHASE delay={delay}: {'ABNORMAL at query #%d'%bad if bad else 'all 80 normal'}; reply time min/avg/max = {min(durs):.2f}/{sum(durs)/len(durs):.2f}/{max(durs):.2f}s")
    if bad:
        rec=wait_recover()
        log(f"  recovery: {'%.0fs'%rec if rec else 'NOT RECOVERED within 120s'}")
        if rec is None: log("STOP: projector not recovered"); break
    else: time.sleep(5)
log("DONE")
