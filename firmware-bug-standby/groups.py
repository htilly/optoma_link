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
try:
    s=conn(3); p,_=q(s,"~00124 1"); s.close()
except Exception as e: p=("ERR "+str(e)).encode()
log(f"GATE power={p!r}")
if p!=b"OK1\r": log("gate not OK1 -> stop"); sys.exit(0)
total=0
for g in range(1,9):
    s=conn(); durs=[]; bad=None
    for i in range(1,11):
        r,d=q(s,"~0087 3"); durs.append(d); total+=1
        if not (r.startswith(b"Ok172") and r.endswith(b"\r")): bad=(i,r); break
    s.close()
    log(f"GROUP {g}: {'ABNORMAL at query %d: %r'%bad if bad else '10/10 normal'}; reply avg {sum(durs)/len(durs):.2f}s; total IP queries so far {total}")
    if bad: log("STOP at first abnormality"); break
    time.sleep(30)
log("DONE")
