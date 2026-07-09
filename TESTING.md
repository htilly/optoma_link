# Hardware verification checklist

Click-through test plan for promoting a release to stable (e.g. 2.8.0 → 3.0.0).
Run against a physical projector; check items off as they pass. File an issue
for anything that fails and note the issue number next to the item.

Fill in for each run:

| | |
|---|---|
| Integration version | |
| Projector model | |
| Firmware (DDP / MCU / Scalar) | |
| Transport | LAN / serial |
| Poll interval used | |
| Lamp hours at start / end | |
| Date, tester | |

## 1. Setup & connection

- [ ] Fresh install: integration discovered in HACS / added manually, config flow completes
- [ ] Model auto-detected correctly (or dropdown fallback works)
- [ ] Test pattern step shows and clears the grid
- [ ] Eco-standby warning appears when the projector is in Eco standby (and not otherwise)
- [ ] Device card populated at startup: firmware version, serial number, MAC address
- [ ] "Visit" link opens the projector's web UI (LAN entries only)
- [ ] Setup with projector unreachable → integration retries and recovers once reachable
- [ ] (If hardware available) serial/RS232 transport connects and behaves like LAN

## 2. Power & status

- [ ] Power on from HA → projector starts; Status: *Warming up* → *On* (push-driven, near-instant)
- [ ] Power off from HA → Status: *Cooling down* → *Off*
- [ ] Power on/off from the **remote** → HA follows via push without polling delay
- [ ] Power state survives an HA restart (correct after startup)

## 3. Picture modes (select each from HA; verify the projector actually switches)

SDR content:
- [ ] Bright — [ ] Cinema — [ ] Reference — [ ] AI-PQ — [ ] Game — [ ] Vivid — [ ] Sport
- [ ] Filmmaker Mode (write 54, reads back as 52)
- [ ] Change mode from the **remote** → HA read-back matches within one poll cycle

HDR content:
- [ ] HDR — [ ] HLG — [ ] Filmmaker Mode
- [ ] HDR10+ (**known gap:** no confirmed read code — sensor may show a raw number; note the number here: ___ and update the profile)

Dolby Vision content:
- [ ] Dolby Vision Bright (reads back 45) — [ ] Dark (46) — [ ] Vivid (47)
- [ ] Selecting a DV mode while playing SDR → clear conflict error message
- [ ] Selecting Filmmaker while in DV → clear rejection message

## 4. 3D (requires 1080p source)

- [ ] 3D switch on → projector enters 3D; Picture Mode / Resolution refresh shortly after
- [ ] 3D Format options apply (Auto / SBS / Top-Bottom / Frame Sequential …)
- [ ] 3D Sync Invert toggles (remember: protocol value 0 = On)
- [ ] 3D commands with a 4K source → friendly error (not a bare failure)
- [ ] Automation check: switching Picture Mode to 3D from HA can trigger an automation (e.g. Light Source Power 100%)

## 5. Image settings

- [ ] Brightness slider applies and reads back after remote-side change
- [ ] Contrast applies and reads back
- [ ] Sharpness applies (write-only; starts at seeded 8 — cosmetic, not read from projector)
- [ ] Aspect Ratio options apply and read back
- [ ] Light Source Power percentages apply (write-only; blank until first set — expected)
- [ ] Dynamic Black 1/2/3 options apply (separate command underneath)
- [ ] AV Mute / Audio Mute toggle and read back
- [ ] Image Freeze holds the frame; note it clears when the input changes

## 6. Inputs

- [ ] HDMI1 / HDMI2 / HDMI3 each switch from HA and read back
- [ ] Input changed from the remote → HA follows within one poll cycle

## 7. Sensors

- [ ] Light Source Hours plausible and increasing
- [ ] System Temperature plausible; Temperature Status = Normal
- [ ] Resolution and Refresh Rate match the active signal
- [ ] Status sensor shows all five states across a power cycle
- [ ] Diagnostic sensors (Serial, Projector ID, IP) disabled by default

## 8. Polling behavior

- [ ] Disable a sensor (e.g. Resolution) → its query disappears from the cycle (verify with debug logging: `custom_components.optoma_link: debug`)
- [ ] Re-enable it → polling resumes
- [ ] Projector off → poll interval relaxes (≥ 60 s between cycles in the log)
- [ ] Power on (remote) → fast polling resumes immediately after the push
- [ ] Changing the poll interval in options applies without a restart
- [ ] **IP Address sensor stays disabled → `~XX87 3` never appears in the debug log** (firmware crash guard, see README known issues)
- [ ] (Optional, UHZ68LV) enable the IP sensor briefly → sensor populates; expect the firmware crash toast eventually (~1 in 20 reads) → disable again and confirm the query stops

## 9. Resilience

- [ ] Unplug network cable → entities become unavailable within ~2 poll cycles
- [ ] Plug back in → recovers automatically within seconds, values return
- [ ] Restart HA with projector on → all values repopulate; no duplicate devices
- [ ] Restart HA with projector in standby → integration loads; device details retry once the projector wakes

## 10. Services

- [ ] `optoma_link.send_command` returns a reply (e.g. code `123` value `1`)
- [ ] `optoma_link.set_test_pattern` shows/hides the grid

## 11. Long-run stability (the 3.0.0 gate)

- [ ] ≥ 1 month of normal use on this build
- [ ] Zero `ProjectorService` crash toasts observed with default entities (lamp-hour delta: ___ h)
- [ ] No unexplained unavailability, stale values, or shifted/cross-field readings
- [ ] No error spam in the HA log

**Sign-off:** all sections pass on hardware → bump to the stable version, mark the profile `verified`, update the README status banner, publish the release.
