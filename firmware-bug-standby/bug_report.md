# Bug report: UHZ68LV ProjectorService crashes on repeated `~XX87 3` queries; LAN control unreliable in standby

## Summary

Two findings on an Optoma UHZ68LV, using only the documented RS232-by-Telnet ASCII protocol (TCP port 23) and a minimal Python script (standard library only).

1. **Reproduced (projector on): repeated IP-address queries `~0087 3` crash `ProjectorService`.** Sending the query repeatedly makes replies slow, then truncated, then absent. The projector shows the on-screen message **"ProjectorService: Central Service has been disconnected, probably crash or something!"** This happened repeatedly: about nine abnormal events in a 20-minute session. It is not limited to older firmware: the unit tested has DDP C24 / MCU M12 / Scalar S34 (see Environment).
2. **Partly observed (standby): LAN control behaves oddly after a non-power query, but Power On over LAN still worked.** In standby with Power Mode = Communication, a firmware query (`~00122 1`) was answered, while a MAC query (`~00555 1`) got no reply. In both runs, a first query on a *new* TCP connection got no reply within 5 s. `~0000 1` (Power On) was nevertheless acknowledged and the projector powered on by itself, without the IR remote. **We did not reproduce a state where only the IR remote or keypad can recover LAN control.**

## Environment

| | |
|---|---|
| Model | Optoma UHZ68LV |
| Firmware (reply to `~00122 1`) | `C24M12S34`. Read from the Menu > Information screen: DDP: ____ / MCU: ____ / Scalar: ____ / LAN: ____ |
| Region (service menu) | non-EMEA |
| Power Mode (Standby) | Communication |
| Connection | LAN, RS232 by Telnet, TCP port 23, projector ID 00 |
| Controller | Python script, one TCP client at a time. The Home Assistant integration was disabled during the tests. |

## Finding 1: IP-address query crashes ProjectorService (projector on)

Setup: projector on (`~00124 1` returns `OK1`), one TCP connection to port 23, repeated `~0087 3\r` queries. Home Assistant integration disabled. Scripts: `bisect.py`, `groups.py`.

| Run | Result |
|---|---|
| Single query | `Ok172_016_205_161`, about 0.35 s. Normal afterwards. |
| 25 rounds, new connection each, 0.5 s between queries, 3 s between rounds (18:16) | 25 of 25 normal. Replies about 0.11 s. |
| Burst A, no pause (18:19) | Query no. 9 got no reply, then `Broken pipe` on the next connection. |
| Burst B, no pause (18:20) | Replies slowed to about 0.9 s, query 7 arrived without its trailing `\r`, query 8 got no reply. |
| `bisect.py`, 1 s between queries (18:23) | Reply no. 44 truncated (no trailing `\r`). LAN answered again after 15 s. |
| `bisect.py`, 0.5 s (18:24) | Reply no. 15 truncated. One power query got no reply, LAN back after 23 s. |
| `bisect.py`, 0.25 s (18:25) | Reply no. 33 truncated. |
| `bisect.py`, 0.1 s (18:26) | Reply no. 50 truncated. One power query got no reply, LAN back after 23 s. |
| `bisect.py`, 0 s (18:27) | Reply no. 37 truncated. One power query got no reply. |
| `groups.py`: 10 queries per new connection, 30 s between groups (18:28-18:33) | Groups 1-7 (70 queries) normal. Group 8, first query (no. 71 in total): truncated reply. A power query at 18:37:32 got no reply (timeout), at 18:38:39 `OK1`. |

What the data supports:

- The first sign in most runs is a **truncated reply**: `Ok172_016_205_161` without the trailing carriage return. A missing reply or a broken connection follows, and LAN control answers again after roughly 5-25 s.
- The failure comes after **15-71 IP queries**, with no fixed number, and it also happens with 30 s pauses between small groups. A fast burst is therefore not required. The pause between queries is not a reliable workaround.
- Reply time grows during a series: about 0.11 s at first, 0.4-0.9 s after the first failures. The effective query rate in the fast phases was bounded by this reply time (about 1 query/s), so we could not test faster tempos.
- The on-screen message **"ProjectorService: Central Service has been disconnected, probably crash or something!"** was seen on several of these occasions. It is visible for only 1-2 s, so not every event was observed. A truncated reply on its own is not proof of the message.

The on-screen message is shown in the attached photo.

Expected: the query should answer every time, or return `F`. It must not take down `ProjectorService`.

## Finding 2: standby behaviour (Power Mode = Communication)

In all runs the projector was off and `~00124 1` returned `OK0` before the test. The standby time before each run was not timed exactly (several minutes in the later runs).

| Test | Result |
|---|---|
| Power query only, 10 fresh connections, 2 queries each | 10 of 10 returned `OK0` for both queries. On some connections the first reply took about 2 s. |
| `~00122 1` (firmware) in standby | Answered: `OKC24M12S34`. Power queries on the same connection still returned `OK0`. |
| ...then a power query on a **new** connection | No reply within 5 s. |
| ...then `~0000 1` (Power On) | Acknowledged (`OK0`). Projector powered on without the remote. A `P` status and `INFO1` followed about 20 s later. |
| `~00555 1` (MAC) in standby | No reply within 5 s. |
| ...then a power query on the same connection | `F` once, then `OK0` twice. |
| ...then a power query on a **new** connection | No reply within 5 s. |
| ...then `~0000 1` (Power On) | Acknowledged (`OK0`). Projector powered on without the remote. |

What we can and cannot say:

- A non-power query in standby can leave the **next new connection** without a reply for at least 5 s. It is not established whether that reply is delayed or lost, because the power-only probe also showed first replies of up to 2 s.
- Power On over LAN worked both times. We could therefore **not** confirm that LAN control stays dead until the IR remote or keypad is used.
- `~00353 1` (serial number) was only run with the projector on, not in standby.

## Impact

- Network controllers that poll `~0087 3` repeatedly can crash `ProjectorService` on the projector. Recovery behaviour after the crash is not fully described here: LAN control answered again in burst run B but the connection broke in burst run A.
- In standby, a new connection's first reply can be missing, which makes controllers see the projector as unreachable.

## Test output

Logs from the session are in this folder:

- `probe.txt`: power-only probe, 10 rounds
- `trigger_122.txt`: standby, `~00122 1`
- `trigger_555.txt`: standby, `~00555 1`
- `ip_query_test.txt`: single `~0087 3`
- `ip_query_series.txt`: 25 spaced rounds
- `stress_test2.txt`: burst run A
- `burst_repro.txt`: burst run B (with millisecond timestamps)
- `bisect_run.txt`: five phases with different pauses (script: `bisect.py`)
- `groups_run.txt`: 10-query groups with 30 s pauses (script: `groups.py`)

Excerpt, burst run B:

```
[18:20:12.327] GATE power=b'OK1\r'
[18:20:12.682] #001 b'Ok172_016_205_161\r'
[18:20:13.610] #002 b'Ok172_016_205_161\r'
...
[18:20:18.098] #007 b'Ok172_016_205_161'
[18:20:21.099] #008 b'NOREPLY'
[18:20:21.099] FIRST ABNORMAL REPLY at query #8
```

## Related issues (separate)

- **EMEA region:** with the region set to EMEA, the LAN and RS232-over-Telnet ports shut down about 20-25 seconds after power-off, even with Power Mode (Standby) = Communication. Changing the region to non-EMEA makes Communication mode work.
