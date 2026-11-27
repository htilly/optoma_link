# Upstream #8 full-poll repro on UHZ68LV C24/M12/S34 (2026-11-27)

Test of the reproduction nerdaxic described in upstream issue #8 (nerdaxic/optoma_link#11, "only the remote brings it back" state), run remotely on the real projector. **Result: not reproduced.** The projector got slow under the full poll but never went silent, and `~0000 1` woke it without the IR remote.

## Setup

| Item | Value |
|---|---|
| Projector | Optoma UHZ68LV, TCP port 23 ("RS232 by Telnet") |
| Firmware | `~00122 1` -> `OKC24M12S34` (DDP C24 / MCU M12 / Scalar S34). nerdaxic: C22/M12/S32 |
| Region / standby mode | non-EMEA, Power Mode (Standby) = Communication (as recorded in `bug_report.md`; not re-checked on 2026-11-27) |
| Client | Linux host on the same LAN, Python 3 raw sockets, `~00<code> <value>\r` |
| HA integration | Optoma Link config entry disabled during both tests, re-enabled afterwards |
| Poll set | `124 1, 355 1, 356 1, 121 1, 123 1, 127 1, 125 1, 126 1, 108 1, 150 18, 155 1, 150 4, 150 19` (UHZ68LV default read set, from `projectors/uhz68lv.json`) |

nerdaxic's recipe: one persistent TCP connection, power off, then every 60 s the full read set back-to-back; silence from `355 1` on, `~0000 1` never lands, recovers only by IR remote (~18 min).

## Test 1: paced poll (not a faithful repro)

Deviations from the recipe, so read it as a weaker test:

- The projector was **already in standby** (`124 1` -> `OK0`), for an unknown time. No power-off was sent.
- The script waited up to 2 s for a reply after each command, so commands went out ~3 s apart, not back-to-back.
- 5 cycles, 60 s apart, then `~0000 1` x2 on the same connection and once on a new connection.

Observed:

- Every second command looked "silent" and the next one returned a stray `F`. This was a script artifact: replies arrived late (>2 s) and were read as the answer to the following command. Cycle 2 shows the backlog arriving at once: `'F\rOK00657\rF\rF\rF\rF\rOK0\r'` (`OK00657` is lamp hours).
- `~0000 1` on the same connection -> `P` (after the backlog), on a new connection -> `P`, `124 1` -> `OK1`. The projector powered on without the IR remote.

Raw log: [Test 1 log](#test-1-log).

## Test 2: back-to-back burst after a real power-off (closest to the recipe)

1. `124 1` -> `OK0` (standby). `~0000 1` -> `P`, waited 100 s, `124 1` -> `OK1`.
2. Opened one persistent connection with a separate reader thread, sent `~0000 0` -> `P`, then `INFO0` ~0.6 s later (power-off acknowledged).
3. 3 s later, 6 cycles, 60 s apart. Each cycle sends all 13 commands in one go without waiting for replies.
4. After cycle 6: `~0000 1` x3 on the same connection, then `124 1` and `~0000 1` on a new connection.

Observed:

- **Cycle 1:** the first six replies came within ~4 s and looked normal (`OK0`, `Ok0`, `Ok0`, `Ok9`, `Ok14`, `Ok0`, i.e. power, AV mute, audio mute, input, picture mode, aspect). `355 1` was **not** silent here, unlike nerdaxic's result.
- **After that the projector slowed down to one reply per ~6.005 s**, almost all `F`, with `OK00657` (lamp hours) once per cycle. 13 commands then take ~78 s, which is longer than the 60 s cycle, so the backlog grew every cycle and replies were increasingly late. The 6.00 s spacing is regular, which points to a fixed internal per-command timeout when the projector is off, not random packet loss.
- The connection stayed open and kept answering until the end. No total silence.
- **Wake:** `~0000 1` x3 on the old connection only got answered behind the backlog. On a **new connection**, `124 1` returned nothing within 3 s (first query on a new connection, consistent with `bug_report.md`), but `~0000 1` right after returned `P` and `INFO1` followed ~10 s later. `124 1` -> `OK1`. The projector powered on without the IR remote.

Raw log: [Test 2 log](#test-2-log).

## What this means

- Not reproduced on C24/M12/S34: no state where only the IR remote recovers LAN control. Matches the earlier finding in `bug_report.md` ("We did not reproduce a state where only the IR remote or keypad can recover LAN control").
- A full poll back-to-back in standby does push the projector into a slow state (~6 s per command, mostly `F`). A client that keeps the same connection and keeps polling will queue its own `~0000 1` behind the backlog. Opening a new connection and sending `~0000 1` was enough here.
- The cleanest explanation of nerdaxic's "silent" state that fits this data is the same backlog seen from a client with a short read timeout, but this test cannot show that. His firmware (C22/M12/S32) differs from this unit and his run was ~18 min, this one ~6 min of polling.

## Limits

- One unit, one run per test, 6 cycles (~6 min) of polling vs ~18 min.
- Test 1 did not include a power-off. In test 2 the power-off to first poll was 5 s.
- The reader in test 2 logs replies but does not match them to commands. The mapping in cycle 1 is by order only.
- No IR-remote recovery was needed, so that state was never entered.

## Afterwards

Projector was powered on by the test in both runs and sent `~0000 0` afterwards (`P`). The HA Optoma Link entry was re-enabled and loaded. `switch.projector_power` was not checked after the final power-off.

## Run it yourself

`optoma_full_poll_repro.py` (same folder, Python 3 standard library only) runs test 2 against any projector: `python3 optoma_full_poll_repro.py <projector-ip> [--cycles 6] [--interval 60]`. Disable the Optoma Link integration in HA first, and have the IR remote at hand in case the projector gets stuck. It differs slightly from the script behind the logs below: it also reads the firmware (`122 1`) while the projector is on, before the power-off, and sends power off again at the end. The replies in the log are printed as they arrive, not matched to commands.

```python
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
```

## Test 1 log

```
13:11:06 projector already off, skipping power off
13:11:06 --- cycle 1
13:11:06 124 1 -> 'OK0\r'
13:11:09 355 1 -> <silent>
13:11:12 356 1 -> 'F\r'
13:11:15 121 1 -> <silent>
13:11:18 123 1 -> 'F\r'
13:11:21 127 1 -> <silent>
13:11:24 125 1 -> 'F\r'
13:11:27 126 1 -> <silent>
13:11:30 108 1 -> 'F\r'
13:11:33 150 18 -> <silent>
13:11:36 155 1 -> 'F\r'
13:11:39 150 4 -> <silent>
13:11:42 150 19 -> 'F\r'
13:12:42 --- cycle 2
13:12:42 124 1 -> 'F\rOK00657\rF\rF\rF\rF\rOK0\r'
13:12:45 355 1 -> <silent>
13:12:48 356 1 -> 'F\r'
13:12:51 121 1 -> <silent>
13:12:54 123 1 -> 'F\r'
13:12:57 127 1 -> <silent>
13:13:00 125 1 -> 'F\r'
13:13:03 126 1 -> <silent>
13:13:06 108 1 -> 'F\r'
13:13:09 150 18 -> <silent>
13:13:12 155 1 -> 'F\r'
13:13:15 150 4 -> <silent>
13:13:18 150 19 -> 'F\r'
13:14:18 --- cycle 3
13:14:18 124 1 -> 'F\rOK00657\rF\rF\rF\rF\rOK0\r'
13:14:21 355 1 -> <silent>
13:14:24 356 1 -> 'F\r'
13:14:27 121 1 -> <silent>
13:14:30 123 1 -> 'F\r'
13:14:33 127 1 -> <silent>
13:14:36 125 1 -> 'F\r'
13:14:40 126 1 -> <silent>
13:14:42 108 1 -> 'F\r'
13:14:46 150 18 -> <silent>
13:14:48 155 1 -> 'F\r'
13:14:52 150 4 -> <silent>
13:14:54 150 19 -> 'F\r'
13:15:54 --- cycle 4
13:15:55 124 1 -> 'F\rOK00657\rF\rF\rF\rF\rOK0\r'
13:15:58 355 1 -> <silent>
13:16:01 356 1 -> 'F\r'
13:16:04 121 1 -> <silent>
13:16:07 123 1 -> 'F\r'
13:16:10 127 1 -> <silent>
13:16:13 125 1 -> 'F\r'
13:16:16 126 1 -> <silent>
13:16:19 108 1 -> 'F\r'
13:16:22 150 18 -> <silent>
13:16:25 155 1 -> 'F\r'
13:16:28 150 4 -> <silent>
13:16:31 150 19 -> 'F\r'
13:17:31 --- cycle 5
13:17:31 124 1 -> 'F\rOK00657\rF\rF\rF\rF\rOK0\r'
13:17:34 355 1 -> <silent>
13:17:37 356 1 -> 'F\r'
13:17:40 121 1 -> <silent>
13:17:43 123 1 -> 'F\r'
13:17:46 127 1 -> <silent>
13:17:49 125 1 -> 'F\r'
13:17:52 126 1 -> <silent>
13:17:55 108 1 -> 'F\r'
13:17:58 150 18 -> <silent>
13:18:01 155 1 -> 'F\r'
13:18:04 150 4 -> <silent>
13:18:07 150 19 -> 'F\r'
13:19:07 --- wake attempts on same connection
13:19:07 00 1 -> 'F\rOK00657\rF\rF\rF\rF\rP\r'
13:19:12 00 1 -> 'P\r'
13:19:17 --- wake attempt on fresh connection
13:19:21 124 1 -> 'OK1\r'
13:19:21 00 1 -> 'P\r'
```

## Test 2 log

```
14:32:12.569 initial power: b'OK0\r'
14:32:19.413 power on -> b'P\r'
14:34:02.829 power now: b'OK1\r'
14:34:03.331 TX power off
14:34:03.775 [main] RX b'P\r'
14:34:04.386 [main] RX b'INFO0\r'
14:34:06.332 --- burst cycle 1: sending 13 commands back-to-back
14:34:06.338 [main] RX b'OK0\r'
14:34:06.516 [main] RX b'Ok0\r'
14:34:07.426 [main] RX b'Ok0\r'
14:34:08.326 [main] RX b'Ok9\r'
14:34:09.225 [main] RX b'Ok14\r'
14:34:10.126 [main] RX b'Ok0\r'
14:34:16.131 [main] RX b'F\r'
14:34:22.136 [main] RX b'F\r'
14:34:22.141 [main] RX b'OK00657\r'
14:34:28.147 [main] RX b'F\r'
14:34:34.153 [main] RX b'F\r'
14:34:40.159 [main] RX b'F\r'
14:34:46.165 [main] RX b'F\r'
14:35:06.332 --- burst cycle 2: sending 13 commands back-to-back
14:35:06.338 [main] RX b'OK0\r'
14:35:12.345 [main] RX b'F\r'
14:35:18.351 [main] RX b'F\r'
14:35:24.358 [main] RX b'F\r'
14:35:30.363 [main] RX b'F\r'
14:35:36.368 [main] RX b'F\r'
14:35:42.374 [main] RX b'F\r'
14:35:48.380 [main] RX b'F\r'
14:35:48.384 [main] RX b'OK00657\r'
14:35:54.390 [main] RX b'F\r'
14:36:00.395 [main] RX b'F\r'
14:36:06.332 --- burst cycle 3: sending 13 commands back-to-back
14:36:06.401 [main] RX b'F\r'
14:36:12.408 [main] RX b'F\r'
14:36:12.412 [main] RX b'OK0\r'
14:36:18.417 [main] RX b'F\r'
14:36:24.424 [main] RX b'F\r'
14:36:30.431 [main] RX b'F\r'
14:36:36.436 [main] RX b'F\r'
14:36:42.441 [main] RX b'F\r'
14:36:48.446 [main] RX b'F\r'
14:36:54.452 [main] RX b'F\r'
14:36:54.458 [main] RX b'OK00657\r'
14:37:00.464 [main] RX b'F\r'
14:37:06.332 --- burst cycle 4: sending 13 commands back-to-back
14:37:06.469 [main] RX b'F\r'
14:37:12.475 [main] RX b'F\r'
14:37:18.480 [main] RX b'F\r'
14:37:18.484 [main] RX b'OK0\r'
14:37:24.489 [main] RX b'F\r'
14:37:30.495 [main] RX b'F\r'
14:37:36.501 [main] RX b'F\r'
14:37:42.506 [main] RX b'F\r'
14:37:48.511 [main] RX b'F\r'
14:37:54.518 [main] RX b'F\r'
14:38:00.523 [main] RX b'F\r'
14:38:00.527 [main] RX b'OK00657\r'
14:38:06.333 --- burst cycle 5: sending 13 commands back-to-back
14:38:06.534 [main] RX b'F\r'
14:38:12.540 [main] RX b'F\r'
14:38:18.545 [main] RX b'F\r'
14:38:24.551 [main] RX b'F\r'
14:38:24.555 [main] RX b'OK0\r'
14:38:30.560 [main] RX b'F\r'
14:38:36.566 [main] RX b'F\r'
14:38:42.572 [main] RX b'F\r'
14:38:48.578 [main] RX b'F\r'
14:38:54.584 [main] RX b'F\r'
14:39:00.589 [main] RX b'F\r'
14:39:06.333 --- burst cycle 6: sending 13 commands back-to-back
14:39:06.594 [main] RX b'F\r'
14:39:06.599 [main] RX b'OK00657\r'
14:39:12.606 [main] RX b'F\r'
14:39:18.610 [main] RX b'F\r'
14:39:24.617 [main] RX b'F\r'
14:39:30.625 [main] RX b'F\r'
14:39:30.629 [main] RX b'OK0\r'
14:39:36.634 [main] RX b'F\r'
14:39:42.640 [main] RX b'F\r'
14:39:48.645 [main] RX b'F\r'
14:39:54.651 [main] RX b'F\r'
14:40:00.657 [main] RX b'F\r'
14:40:06.333 --- wake attempts, same connection
14:40:06.663 [main] RX b'F\r'
14:40:12.669 [main] RX b'F\r'
14:40:12.673 [main] RX b'OK00657\r'
14:40:18.680 [main] RX b'F\r'
14:40:24.688 [main] RX b'F\r'
14:40:27.742 --- fresh connection 124 1 -> b''
14:40:30.707 [main] RX b'F\r'
14:40:36.757 [main] RX b'F\r'
14:40:36.785 --- fresh connection 00 1 -> b'P\r'
14:40:36.809 [main] RX b'P\r'
14:40:36.833 [main] RX b'P\r'
14:40:36.857 [main] RX b'P\r'
14:40:46.514 [main] RX b'INFO1\r'
14:41:00.203 final power: b'OK1\r'
```
