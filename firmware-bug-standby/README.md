# UHZ68LV firmware bug: LAN control goes silent in standby

Working folder for verifying a firmware bug on a real projector and reporting it to Optoma. It is **not** part of the integration and is not meant for upstream.

> **Claude, if you were pointed here:** read this whole file first. The job is in
> [Your task](#your-task-claude). The session must run on (or be attached to) a computer on the
> same LAN as the projector. A cloud container can't reach it.

## Symptom (what the owner sees)

Quite often after Home Assistant restarts, HA cannot power the projector on. Powering it on once with the IR remote makes everything work normally again, until the next HA restart.

## Root cause: two parts

### 1. Firmware bug (Optoma's to fix)

In standby (Power Mode (Standby) = *Communication*, region = non-EMEA), the LAN "RS232 by Telnet" port (TCP 23):

- answers the power-status query `~00124 1` → `Ok0` reliably, **but**
- after **any other read query** (for example `~00122 1` firmware, `~00555 1` MAC, `~00353 1` serial), it goes **silent to every command**, Power On `~0000 1` included. A new TCP connection does not help. Only powering on by IR remote or keypad recovers it.

This was found upstream and documented in commit `eae053a` ("Poll only power while the projector is off (#8)"). **It has not yet been verified independently with a minimal script.** That is the point of this folder.

### 2. Integration hole (our side, makes the firmware bug fire after HA restarts)

Since 2.9.1 the integration avoids the bug by sending only the power query while the projector is off. The guard is `_is_standby()` in `custom_components/optoma_link/coordinator.py`:

```python
return data.get("power") is False
```

Right after an HA restart `data` is empty, so `power` is `None`, not `False`. If the **first** power query after the restart doesn't return a clean `Ok0`, nothing is blocked:

- **`F` reply** in `async_fetch_device_details()` → `power` stays `None` → it reads firmware (`122`), MAC (`555`) and serial (`353`) → the firmware bug fires.
- **Timeout** in `_async_update_data()` → the error is recorded, the loop continues, and **every enabled read** is sent, because `power` is still not `False`.

**Planned fix (not done yet):** send non-power reads (entity reads and device details) only when power is *confirmed on*: `power is True` or `status in ("on", "warming_up")`. Profiles with no power read keep today's behaviour. Add tests in `tests/test_coordinator.py`.

## Files

| File | Purpose |
|---|---|
| `optoma_standby_test.py` | Test script. Python 3 standard library only, no dependencies. |
| `bug_report.md` | Bug report for Optoma (English). Firmware versions and test output still to fill in. |
| `mock_projector.py` | Fake projector **with** the bug, on `127.0.0.1:23230`, for checking the script without hardware. |

### Test modes

```bash
# A) Reproduce the firmware bug. Leaves the projector stuck: recover with the IR remote.
python3 optoma_standby_test.py <projector-ip>
python3 optoma_standby_test.py <projector-ip> --query "555 1"    # if 122 1 doesn't trigger it

# B) Safe probe: power queries only, each on a fresh connection.
#    Shows whether the FIRST query after connecting gets F or no reply (part 2 above).
python3 optoma_standby_test.py <projector-ip> --mode connect-probe --rounds 10

# Self-test without hardware
python3 mock_projector.py &  python3 optoma_standby_test.py 127.0.0.1 --port 23230 --timeout 2
```

## Preconditions for every hardware test

1. **Disable the Optoma Link integration in HA** (Settings → Devices & services → Optoma Link → ⋮ → Disable). Otherwise HA is connected at the same time, and the projector may allow only one Telnet session.
2. Check on the projector: Power Mode (Standby) = **Communication**, region = **non-EMEA**. Note the firmware versions under Menu → Information (DDP / MCU / Scalar / LAN).
3. Power the projector off and wait about **2 minutes**, until it is fully in standby.
4. Re-enable the integration when you are done.

## Your task (Claude)

1. Confirm the projector is reachable: ask the owner for its IP (it is also in the HA config entry), then run `nc -zv <ip> 23` or the equivalent. Confirm the preconditions above **with the owner**. The owner has to do the HA disable step and the remote-control recovery.
2. Run **mode B (connect-probe)** first, because it is safe. Save the output.
3. Run **mode A (trigger)**. If it says `NOT REPRODUCED`, retry with `--query "555 1"` and `--query "353 1"`. Ask the owner to recover with the IR remote and wait for standby again between runs. Save every output.
4. Ask the owner whether the projector physically powered on in step 5 of mode A.
5. Fill in `bug_report.md`: the firmware versions, and the real test output in "Test output". Adjust the wording to match what was actually observed. **Don't claim anything the tests didn't show.** If the bug did not reproduce, say so and stop before sending anything to Optoma.
6. Report the mode B result. It tells whether part 2 (the integration hole) is real on this unit. Then offer to implement the planned integration fix.
7. Commit the updated files to the working branch and push. Sending the report to Optoma is the owner's call.

## Related, already known

- **EMEA region:** the LAN port shuts off in standby even with *Communication*. See the README's "Known issues" and PR #11 upstream.
- **`~XX87 3` (IP address query)** intermittently crashes `ProjectorService` on DDP C22 / MCU M12 / Scalar S32. See upstream issue #1.
