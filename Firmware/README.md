# Frostbite firmware (QMK)

QMK keyboard for Frostbite 9 in `qmk/keyboards/frostbite/`: Seeed XIAO RP2040, 3x3 keys, EC11 encoder, 0.91" 128x32 SSD1306 OLED at `0x3C` and 13 SK6812 MINI-E LEDs. Keymap `default` is the Raw HID dashboard with keyboard fallback (`production/firmware.uf2`). Keymap `ledtest` is the bring-up test (`production/led-test.uf2`). `../design.json` is the source of truth. USB VID/PID are test values: `0xFEED` / `0x4642`.

| Function | XIAO | GPIO |
|---|---|---|
| Rows 0-2 | D0, D1, D2 | GP26, GP27, GP28 |
| Columns 0-2 (COL2ROW) | D3, D9, D10 | GP29, GP4, GP3 |
| OLED SDA / SCL (I2C1) | D4 / D5 | GP6 / GP7 |
| LED data (PIO) | D6 | GP0 |
| Encoder A / B | D7 / D8 | GP1 / GP2 |

## Build

```sh
ln -sfn "$PWD/qmk/keyboards/frostbite" ~/qmk_firmware/keyboards/frostbite   # once, from Firmware/
qmk lint -kb frostbite
qmk compile -kb frostbite -km default && cp ~/qmk_firmware/frostbite_default.uf2 ../production/firmware.uf2
qmk compile -kb frostbite -km ledtest && cp ~/qmk_firmware/frostbite_ledtest.uf2 ../production/led-test.uf2
```

## Flash

1. Put the XIAO in its UF2 bootloader, one of:
   - Hold the XIAO **BOOT** button while plugging in USB. Use this for the first flash: the other two ways need the Frostbite firmware on the XIAO already.
   - Double-tap the XIAO **RESET** button.
   - Hold **Approve + Stop** (bottom-left and bottom-right keys) while plugging in. This also clears EEPROM. Both keys are needed: `bootmagic_should_reset` in `frostbite.c` replaces the single-key default named in `keyboard.json`.
2. A drive named **RPI-RP2** appears. Drag `firmware.uf2` (or `led-test.uf2`) onto it. The board reboots by itself.

For bring-up, flash `led-test.uf2` before soldering switches. Each LED lights red, green, blue, then white in chain order while the OLED shows `LED TEST n/13`. If LED n works but n+1 never lights, check LED n's DOUT, LED n+1's DIN, and its 5 V and GND. The test build also shows the last key pressed (`key: rR cC`) and an encoder count, so the OLED and knob can be checked as soon as J1 is soldered, before the PCB goes into the case.

## Known risks

- **LED data**: the XIAO drives 3.3 V data into a 5 V SK6812 chain. This is marginal (VIH about 3.5 V), and `led-test.uf2` proves it at bring-up.
- **OLED orientation**: the display is rotated 180 degrees because the header sits at the right end of the module, and four reference Hackpads with that placement flip it. This is unconfirmed on a fitted module. If the text is upside down, comment out `#define FROSTBITE_OLED_FLIP` in `config.h` and rebuild.
- **Encoder**: unmeasured on the kit part. `encoder.rotary[0].resolution` in `keyboard.json` is transitions per step, currently 4. Turn the knob in `ledtest` and watch `knob:`. If one detent moves the count by two, double the value. If one count takes two detents, as on a true 30-detent/15-pulse EC11E, set it to 2. If clockwise counts down, swap `pin_a` and `pin_b` and do not resolder; `PCB/tools/check_netlist.py` and verify `G2.firmware_pins` both require `pin_a` on `ENC_A`, so update them too.

## Keymap

| Key | Index | Matrix | LED | Host mode (Raw HID) | Fallback keycode |
|---|---|---|---|---|---|
| Agent 1-6 | 0-5 | rows 0-1 | 0, 1, 2, 5, 4, 3 | KEY n tap/hold, slot n | F13-F18 |
| Approve | 6 | (2,0) | 6 | KEY 6 | F19 |
| Talk | 7 | (2,1) | 7 | KEY 7 and F20, held while held | F20, held while held |
| Stop | 8 | (2,2) | 8 | KEY 8 | Escape |
| Encoder | - | GP1/GP2 | - | select slot 0-5 (wraps), ENCODER event | Volume up / down |

Key index is `row * 3 + col`, the order of `keys[]` in design.json. The LED chain is serpentine across the keys, then the four corners (glow LEDs 9-12). **Talk** always sends F20, so push-to-talk tools work whether or not the host app is running; the host ignores its KEY event on purpose. **Stop** in fallback is a plain Escape to whatever app is in front, with no proof of anything (see `host/README.md`). **Glow** shows the SET_GLOW colour: ice blue `#7fe3ff` at 70 of 255 (about 27 %) with no host, and `glow()` in `host/frostbite_host/state.py` with the daemon running. On macOS, F14 and F15 (Agent 2 and 3 in fallback) may change display brightness; this is untested.

## Raw HID protocol

Usage page `0xFF60`, usage `0x61`, 32-byte reports. Byte 0 is the command and unused bytes are zero. The descriptor has no report IDs, and the OS consumes hidapi's leading `0x00` on writes, so the firmware sees the command first.

| Dir | Cmd | Bytes | Notes |
|---|---|---|---|
| host->dev | `0x01` SET_SLOT | `[01, slot, status]` | status: 0 idle, 1 run, 2 done, 3 needs, 4 error |
| host->dev | `0x02` SET_ALL | `[02, s0..s5]` | |
| host->dev | `0x03` OLED_LINE | `[03, line 0-1, len, <=21 ASCII]` | `len = 0` restores the default text. A shorter string blanks the rest of the line, so the host need not pad. |
| host->dev | `0x04` SET_GLOW | `[04, r, g, b, brightness]` | |
| host->dev | `0x05` PING | `[05]` | reply `[05, 1, selected_slot]` |
| host->dev | `0x06` SET_SELECTED | `[06, slot 0-5]` | |
| dev->host | `0x81` KEY | `[81, key 0-8, 1 tap / 2 hold]` | hold is sent once the key has been down 400 ms, a tap on release if sooner |
| dev->host | `0x82` ENCODER | `[82, 01 cw / FF ccw, selected_slot]` | |

## Host mode

- **Timeout**: host mode lasts while a PING arrived in the last 5 s, so the host should PING every 1-2 s. Without one the pad uses the fallback keycodes, agent LEDs fade to idle over 1.5 s, glow fades to its default, and the OLED shows the no-host screen. Fallback only changes what is displayed. Statuses, OLED text, glow and the selected slot are kept, so the pad returns to the last host state when PINGs resume, without a USB reconnect. The host can send SET_ALL with every PING: matching values change nothing.
- **LEDs**: idle is dim white, run is blue `#3d8bff`, done is green `#2fbf5b`, needs is a slow amber `#ffb020` pulse (2.4 s) and error blinks red `#ff4d4f` (1 Hz). The selected slot is brighter and breathes. Command keys are dim white and brighten while pressed. Colour changes cross-fade, and a simple current limiter keeps total LED output within USB power.
- **OLED**: row 1 is OLED_LINE 0, or `slot N  STATUS` for the selected slot (N is 1-6). Row 2 is OLED_LINE 1, or a summary such as `3 run 1 wait 2 done` once statuses arrive, otherwise a hint. Row 3 is a dotted divider. Do not write text to it: blanking it every frame re-dirties that block and starves row 4 of QMK's one-block-per-loop render. Row 4 is a slot strip (`1- 2R 3D 4? 5! 6-`) with the selected slot inverted and `HID` or `KBD` for the mode. The display turns off after 10 minutes without activity. Only a key, the encoder, a real status change or a USB resume counts. PING, OLED_LINE, SET_GLOW, SET_SELECTED and a repeated SET_ALL neither wake it nor keep it on, though text still updates for the next wake. A USB resume lights it once so a waiting prompt is visible, and the 10-minute timer runs from there.
