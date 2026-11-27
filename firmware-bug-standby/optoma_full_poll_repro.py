#!/usr/bin/env python3
"""Full-poll standby repro for Optoma UHZ68LV LAN control (upstream nerdaxic/optoma_link#8).

Recipe: ONE persistent TCP connection, power off, then every INTERVAL seconds send the
integration's full default read set back-to-back (no waiting for replies). Afterwards try to
wake the projector with ~0000 1, first on the same connection, then on a new one.

Needs only Python 3 (standard library). Run it from a machine on the projector's LAN.

BEFORE YOU RUN
  1. Disable the Optoma Link integration in Home Assistant (the projector may allow only
     one Telnet session, and HA would keep polling).
  2. Set Power Mode (Standby) = Communication and a non-EMEA region, otherwise the LAN port
     shuts down in standby.
  3. Be prepared to wake the projector with the IR remote. If the bug triggers, nothing
     over LAN will bring it back.

The script turns the projector on if it is in standby (so the power-off can be tested), runs
the test, and sends power off again at the end.

Usage:  python3 optoma_full_poll_repro.py <projector-ip> [--cycles 6] [--interval 60]
"""
import argparse
import datetime
import socket
import sys
import threading
import time

READS = ["124 1", "355 1", "356 1", "121 1", "123 1", "127 1", "125 1", "126 1",
         "108 1", "150 18", "155 1", "150 4", "150 19"]  # UHZ68LV default read set


def log(msg):
    print(datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], msg, flush=True)


def send(sock, pid, cmd):
    sock.sendall(f"~{pid}{cmd}\r".encode("ascii"))


def once(host, port, pid, cmd, wait=3.0):
    """Send one command on a fresh connection and return whatever arrives within `wait`."""
    s = socket.create_connection((host, port), timeout=5)
    s.settimeout(wait)
    time.sleep(0.4)
    try:
        s.recv(4096)  # discard banner/prompt, if any
    except OSError:
        pass
    send(s, pid, cmd)
    try:
        out = s.recv(4096)
    except OSError:
        out = b""
    s.close()
    return out


def reader(sock):
    while True:
        try:
            data = sock.recv(4096)
        except OSError as err:
            log(f"[main] recv error: {err}")
            return
        if not data:
            log("[main] closed by projector")
            return
        log(f"[main] RX {data!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", help="projector IP address")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--id", default="00", help="projector ID used in commands (default 00)")
    ap.add_argument("--cycles", type=int, default=6, help="number of full polls (default 6)")
    ap.add_argument("--interval", type=int, default=60, help="seconds between polls (default 60)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a = ap.parse_args()

    if not a.yes:
        print(__doc__.split("BEFORE YOU RUN")[1].split("The script turns")[0])
        if input("Type YES to continue: ").strip() != "YES":
            sys.exit("aborted")

    h, p, pid = a.host, a.port, a.id
    state = once(h, p, pid, "124 1")
    log(f"power state: {state!r}")
    if b"OK0" in state:
        log(f"standby -> power on: {once(h, p, pid, '00 1')!r}; waiting 100 s for warm-up")
        time.sleep(100)
        log(f"power state: {once(h, p, pid, '124 1')!r}")
    log(f"firmware (122 1, read while on): {once(h, p, pid, '122 1')!r}")

    s = socket.create_connection((h, p), timeout=5)
    s.settimeout(None)
    threading.Thread(target=reader, args=(s,), daemon=True).start()
    time.sleep(0.5)

    log("TX power off (persistent connection)")
    send(s, pid, "00 0")
    time.sleep(3)

    for i in range(a.cycles):
        log(f"--- cycle {i + 1}/{a.cycles}: {len(READS)} commands back-to-back")
        for cmd in READS:
            send(s, pid, cmd)
        time.sleep(a.interval)

    log("--- wake attempts on the same connection")
    for _ in range(3):
        send(s, pid, "00 1")
        time.sleep(5)

    log(f"--- new connection, 124 1 -> {once(h, p, pid, '124 1')!r}")
    log(f"--- new connection, 00 1 -> {once(h, p, pid, '00 1', 5)!r}")
    time.sleep(20)
    log(f"--- power state now: {once(h, p, pid, '124 1')!r}  (OK1 = woke up without the IR remote)")

    log(f"--- restoring standby: {once(h, p, pid, '00 0', 5)!r}")
    s.close()


if __name__ == "__main__":
    main()
