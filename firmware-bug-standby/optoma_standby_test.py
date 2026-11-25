#!/usr/bin/env python3
"""Reproduce: Optoma UHZ68LV LAN control goes silent in standby after a non-power query.

Usage (from any machine on the same network as the projector, e.g. the HA host):

    python3 optoma_standby_test.py 192.168.1.50
    python3 optoma_standby_test.py 192.168.1.50 --port 23 --id 00

Before running:
  1. DISABLE the Optoma Link integration in Home Assistant (Settings > Devices &
     services > Optoma Link > ... > Disable), so HA isn't talking to the projector
     at the same time.
  2. Turn the projector OFF and wait ~2 minutes until it is fully in standby.

The test only uses the standard RS232-by-Telnet protocol (Python standard
library, no dependencies). If the bug is present the projector will stop
answering on LAN; power it on with the remote to recover it afterwards.
"""
from __future__ import annotations

import argparse
import socket
import time

T0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - T0:7.2f}s] {msg}", flush=True)


class Link:
    def __init__(self, host: str, port: int, pid: str, timeout: float) -> None:
        self.host, self.port, self.pid, self.timeout = host, port, pid, timeout
        self.sock: socket.socket | None = None
        self.buf = b""

    def connect(self) -> None:
        self.close()
        log(f"TCP connect {self.host}:{self.port}")
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.buf = b""
        # Log anything the projector sends unprompted right after connecting.
        for line in self._lines(wait=1.0):
            log(f"   (unsolicited on connect) {line!r}")

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.sendall(b"Close\r")
            except OSError:
                pass
            self.sock.close()
            self.sock = None
            log("TCP closed")

    def _lines(self, wait: float):
        assert self.sock is not None
        deadline = time.monotonic() + wait
        out = []
        while True:
            while b"\r" in self.buf:
                raw, self.buf = self.buf.split(b"\r", 1)
                text = raw.decode("ascii", "replace").strip()
                if text:
                    out.append(text)
            if out:
                return out
            left = deadline - time.monotonic()
            if left <= 0:
                return out
            self.sock.settimeout(left)
            try:
                chunk = self.sock.recv(1024)
            except socket.timeout:
                return out
            if not chunk:
                log("   !! connection closed by projector")
                return out
            self.buf += chunk

    def send(self, code: str, value: str | None, label: str) -> str | None:
        cmd = f"~{self.pid}{code}" + (f" {value}" if value is not None else "")
        assert self.sock is not None
        log(f"TX {cmd!r:<16} ({label})")
        try:
            self.sock.sendall(cmd.encode("ascii") + b"\r")
        except OSError as err:
            log(f"   !! send failed: {err}")
            return None
        lines = self._lines(wait=self.timeout)
        reply = None
        for line in lines:
            if line.upper().startswith("INFO"):
                log(f"   RX (status push) {line!r}")
            else:
                reply = line
                log(f"   RX {line!r}")
        if reply is None:
            log(f"   -- NO REPLY within {self.timeout:.0f}s")
        return reply


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--id", default="00", help="projector ID (default 00)")
    ap.add_argument("--timeout", type=float, default=5.0, help="seconds to wait per reply")
    ap.add_argument("--query", default="122 1",
                    help="the non-power query to send in standby (default '122 1' = firmware version)")
    ap.add_argument("--mode", choices=("trigger", "connect-probe"), default="trigger",
                    help="trigger = reproduce the firmware bug (default); connect-probe = only "
                         "power queries, each on a fresh TCP connection (safe, does not trigger "
                         "the bug) to see whether the FIRST query after connecting gets F/no reply")
    ap.add_argument("--rounds", type=int, default=10, help="connect-probe: number of connections")
    a = ap.parse_args()
    q_code, _, q_val = a.query.partition(" ")

    link = Link(a.host, a.port, a.id, a.timeout)

    if a.mode == "connect-probe":
        tally: dict[str, int] = {}
        for r in range(a.rounds):
            log(f"=== Round {r + 1}/{a.rounds}: fresh connection, first query = power status ===")
            link.connect()
            first = link.send("124", "1", "power status (first after connect)")
            second = link.send("124", "1", "power status (second)")
            link.close()
            key = f"first={first!r} second={second!r}"
            tally[key] = tally.get(key, 0) + 1
            time.sleep(3)
        print("\n================ CONNECT-PROBE SUMMARY ================")
        for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {v:>3} x  {k}")
        print("\nAnything other than first='Ok0' (in standby) means the first query after a new")
        print("connection is unreliable - which is what lets the HA integration send further")
        print("queries in standby after a restart and trigger the firmware bug.")
        return

    results: dict[str, str | None] = {}

    log("=== Step 1: baseline - power-status query in standby (expect 'Ok0') ===")
    link.connect()
    for i in range(3):
        results[f"baseline_{i}"] = link.send("124", "1", "power status")
        time.sleep(1)

    log(f"=== Step 2: one non-power query in standby: {a.query} ===")
    results["trigger"] = link.send(q_code, q_val or None, "non-power query")
    time.sleep(1)

    log("=== Step 3: power-status query again, same connection ===")
    for i in range(3):
        results[f"after_{i}"] = link.send("124", "1", "power status")
        time.sleep(1)

    log("=== Step 4: power-status query on a NEW TCP connection ===")
    link.connect()
    results["after_reconnect"] = link.send("124", "1", "power status")

    log("=== Step 5: power ON command over LAN ===")
    results["power_on"] = link.send("00", "1", "power on")
    log("Waiting 20 s for the projector to react ...")
    time.sleep(20)
    results["power_after_on"] = link.send("124", "1", "power status")
    link.close()

    baseline_ok = all(results[f"baseline_{i}"] for i in range(3))
    silent_after = not any(results[f"after_{i}"] for i in range(3))
    print()
    print("================ SUMMARY ================")
    for k, v in results.items():
        print(f"  {k:<18} {v!r}")
    print()
    if not baseline_ok:
        print("INCONCLUSIVE: the projector did not answer the power query reliably even before")
        print("the trigger. Check that it is in standby, Power Mode (Standby) = Communication,")
        print("and that nothing else (Home Assistant) is connected.")
    elif silent_after and not results["after_reconnect"]:
        print("BUG REPRODUCED: the projector answered power queries in standby, then went silent")
        print(f"to all LAN commands after a single '{a.query}' query, including after reconnecting.")
        print("Check whether the projector powered on in step 5. Recover with the remote control.")
    elif silent_after:
        print("PARTIAL: silent on the same connection after the trigger, but answered again on a")
        print("new TCP connection.")
    else:
        print("NOT REPRODUCED with this query. Try another, e.g. --query '555 1' (MAC) or '353 1'.")


if __name__ == "__main__":
    main()
