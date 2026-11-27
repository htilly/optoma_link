#!/usr/bin/env python3
"""Reproduce: Optoma UHZ68LV ProjectorService crash on repeated IP-address queries.

Uses only the documented RS232-by-Telnet ASCII protocol (TCP port 23) and the
Python 3 standard library. Tested on firmware C24M12S34 (reply to ~00122 1).

What it does
  1. Gate: sends one power query (~00124 1). Unless the projector is ON ("OK1")
     it sends nothing else and exits.
  2. Sends the IP-address query (~0087 3) repeatedly on ONE connection, with an
     optional delay between queries. Every reply is timestamped.
  3. A reply that does not start with "Ok" or has no trailing carriage return
     counts as abnormal (we saw truncated replies first, e.g. "Ok<ip address>"
     without the trailing \\r), and so does a missing reply.
  4. After the first abnormal reply it keeps querying for up to --after more
     queries or until a query gets no reply, then checks the power query on new
     connections.

Watch the projector's screen while it runs. The on-screen message
  "ProjectorService: Central Service has been disconnected, probably crash or something!"
is visible for only 1-2 seconds. Filming the screen helps.

Before running: disable any other LAN controller (Home Assistant, Crestron, ...)
so only one client talks to the projector. The projector must be ON.

Usage
  python3 repro_ip_query_crash.py <projector-ip>
  python3 repro_ip_query_crash.py <projector-ip> --delay 1 --max 200 --start-in 30

In our tests the first abnormal reply came after 15-71 queries (about 10-60 s)
at every pause length from 0 s to 1 s. LAN control came back after about 5-25 s.
The projector may be unreachable for a while afterwards; this is the bug.
"""
import argparse
import socket
import sys
import time


def log(msg):
    t = time.time()
    print(f"[{time.strftime('%H:%M:%S', time.localtime(t))}.{int(t % 1 * 1000):03d}] {msg}", flush=True)


def connect(host, port, timeout):
    s = socket.create_connection((host, port), timeout=timeout)
    s.settimeout(timeout)
    return s


def query(sock, cmd, timeout):
    sock.settimeout(timeout)
    t0 = time.time()
    try:
        sock.sendall(cmd.encode() + b"\r")
        reply = sock.recv(256)
    except Exception as exc:  # timeout, reset, broken pipe, ...
        reply = b"NOREPLY/" + type(exc).__name__.encode()
    return reply, time.time() - t0


def power(host, port, pid, timeout=4):
    try:
        s = connect(host, port, timeout)
        reply, _ = query(s, f"~{pid}124 1", timeout)
        s.close()
        return reply
    except Exception as exc:
        return b"ERR/" + type(exc).__name__.encode()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--id", default="00", help="projector ID (default 00)")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds between IP queries (default 0)")
    ap.add_argument("--max", type=int, default=200, help="maximum IP queries (default 200)")
    ap.add_argument("--after", type=int, default=12, help="extra queries after the first abnormal reply (default 12)")
    ap.add_argument("--timeout", type=float, default=3.0, help="seconds to wait per reply (default 3)")
    ap.add_argument("--start-in", type=int, default=0, help="wait this many seconds first, e.g. to get a camera ready")
    a = ap.parse_args()
    pid = a.id

    if a.start_in:
        log(f"starting in {a.start_in} s")
        time.sleep(a.start_in)

    p = power(a.host, a.port, pid)
    log(f"GATE power={p!r}")
    if p != b"OK1\r":
        log("projector is not ON (expected 'OK1'): sending nothing more")
        return 1

    log(f"BURST START: ~{pid}87 3, delay {a.delay}s, one connection")
    s = connect(a.host, a.port, a.timeout)
    first_bad = None
    for i in range(1, a.max + 1):
        reply, dt = query(s, f"~{pid}87 3", a.timeout)
        ok = reply.startswith(b"Ok") and reply.endswith(b"\r")
        if i % 10 == 0 or not ok:
            log(f"  #{i:03d} {reply!r} ({dt:.2f}s)")
        if not ok and first_bad is None:
            first_bad = i
            log(f"FIRST ABNORMAL REPLY at query #{i}")
        if first_bad is not None and (reply.startswith(b"NOREPLY") or i - first_bad >= a.after):
            log(f"STOP at query #{i}: watch the screen now")
            break
        time.sleep(a.delay)
    else:
        log(f"no abnormal reply in {a.max} queries")
    try:
        s.close()
    except Exception:
        pass

    time.sleep(2)
    for _ in range(3):
        log(f"after: power={power(a.host, a.port, pid)!r}")
        time.sleep(3)
    return 0 if first_bad is not None else 2


if __name__ == "__main__":
    sys.exit(main())
