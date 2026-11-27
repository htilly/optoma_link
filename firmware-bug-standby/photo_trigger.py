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
log("armed - burst starts in 20 s"); time.sleep(20)
try:
    s=conn(3); p,_=q(s,"~00124 1"); s.close()
except Exception as e: p=("ERR "+str(e)).encode()
log(f"GATE power={p!r}")
if p!=b"OK1\r": log("gate not OK1 -> sending nothing"); sys.exit(0)
log("BURST START")
s=conn()
for i in range(1,201):
    r,d=q(s,"~0087 3")
    if i%10==0: log(f"  #{i} {r!r} {d:.2f}s")
    if not (r.startswith(b"Ok172") and r.endswith(b"\r")):
        log(f"TRIGGERED at query #{i}: {r!r}  <-- text should be on screen now for 1-2 s"); break
else: log("no failure in 200 queries")
try: s.close()
except: pass
log("DONE")
