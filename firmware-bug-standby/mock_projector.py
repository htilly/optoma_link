"""Fake UHZ68LV on 127.0.0.1:23230 that HAS the standby bug: answers ~00124 1 with Ok0
until it gets any other command, then stays silent to everything. For testing
optoma_standby_test.py without hardware."""
import socket,threading
poison=False
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(("127.0.0.1",23230));s.listen()
def h(c):
    global poison
    buf=b""
    while True:
        d=c.recv(100)
        if not d: return
        buf+=d
        while b"\r" in buf:
            l,buf=buf.split(b"\r",1)
            if poison or l==b"Close": continue
            if l==b"~00124 1": c.sendall(b"Ok0\r")
            else: poison=True
while True:
    c,_=s.accept();threading.Thread(target=h,args=(c,),daemon=True).start()
