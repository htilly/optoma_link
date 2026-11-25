# Bug report: UHZ68LV LAN control (RS232 by Telnet) stops responding in standby after a non-power query

## Summary

In standby, the projector's LAN control port ("RS232 by Telnet", TCP port 23) answers the power-status query (`~00124 1` → `Ok0`) reliably. But as soon as it receives **any other read query** while in standby (for example the firmware version `~00122 1`), the LAN control stops responding to **every** command, including Power On (`~0000 1`). Opening a new TCP connection does not help. The projector only recovers after it is powered on with the IR remote or the keypad. After that, LAN control works normally again.

As a result, network control systems (home automation, Crestron/Control4-style controllers and so on) cannot reliably power the projector on, which is the main reason to have network control.

## Environment

| | |
|---|---|
| Model | Optoma UHZ68LV |
| Firmware | DDP: ____ / MCU: ____ / Scalar: ____ / LAN: ____ *(Menu > Information)* |
| Region (service menu) | non-EMEA *(with EMEA the LAN port shuts off completely in standby; see "Related" below)* |
| Power Mode (Standby) | Communication |
| Connection | LAN, RS232 by Telnet, TCP port 23, projector ID 00 |
| Controller | Any TCP client. Reproduced with a minimal Python script (attached) using only the documented RS232 ASCII protocol. |

## Steps to reproduce

1. Set Power Mode (Standby) to **Communication**.
2. Power the projector off and wait about 2 minutes until it is in standby.
3. Open a TCP connection to port 23.
4. Send `~00124 1\r` several times. **Result:** `Ok0` every time (correct).
5. Send one other read query, for example `~00122 1\r` (firmware version). Other reads such as `~00555 1` (MAC) and `~00353 1` (serial number) behave the same way.
6. Send `~00124 1\r` again. **Result:** no reply.
7. Close the connection, open a new one and send `~00124 1\r`. **Result:** no reply.
8. Send `~0000 1\r` (Power On). **Result:** no reply, and the projector does not power on.
9. Press Power on the IR remote. The projector powers on, and LAN control responds normally again from then on.

## Expected behaviour

In standby with Power Mode = Communication, the projector should either answer each query (with the value, or with `F` if it is not available in standby) or ignore it. In every case it should keep responding to later commands, above all **Power On**. A single unsupported query must not disable the control interface.

## Actual behaviour

After one non-power query in standby, the LAN control interface stops responding entirely until the projector is powered on locally (with the IR remote or keypad).

## Test output

*(Paste the output of `optoma_standby_test.py` here: the trigger run, and the `--mode connect-probe` run if relevant.)*

```
```

## Impact

- The projector cannot be powered on over the network after a controller has sent any status query in standby. Controllers commonly do this, for example when they reconnect after a reboot and refresh their state.
- The failure is silent. The controller has no way to detect or recover from it.
- The only workarounds are on the controller side: never send anything but the power query while the projector might be in standby, or power the projector on by IR or HDMI-CEC instead.

## Related issues (separate)

- **EMEA region:** with the region set to EMEA, the LAN and RS232-over-Telnet ports shut down about 20–25 seconds after power-off, even with Power Mode (Standby) = Communication. The setting is accepted and reads back correctly. Changing the region to non-EMEA in the service menu makes Communication mode work. If this is meant to meet EU standby-power rules, the menu should not offer or accept Communication mode in that region, or it should document the limitation.
- **IP address query:** on firmware DDP C22 / MCU M12 / Scalar S32, the query `~XX87 3` intermittently (about 1 in 20 calls) crashes `ProjectorService` ("Central service has been disconnected" toast). This was reported earlier.
