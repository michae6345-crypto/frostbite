# Frostbite firmware

This is the QMK firmware for Frostbite 9. It lives in `qmk/keyboards/frostbite/`. `../design.json` is the source of truth.

The pad is a Seeed XIAO RP2040 with 3x3 keys, an EC11 encoder and a 0.91" 128x32 SSD1306 OLED at `0x3C`. The pad has no lights. All status is on the OLED.

There are two keymaps:

| Keymap | File | Use |
|---|---|---|
| `default` | `production/firmware.uf2` | Raw HID dashboard with a keyboard fallback |
| `bringup` | `production/bringup.uf2` | Checks each key, the dial direction and the OLED |

USB VID and PID are `0xFEED` and `0x4642`. These are test values. The host filters on them.

## Pins

| XIAO | GPIO | Net | Function |
|---|---|---|---|
| D0 | GP26 | ROW0 | Matrix row 0 |
| D1 | GP27 | ROW1 | Matrix row 1 |
| D2 | GP28 | ROW2 | Matrix row 2 |
| D3 | GP29 | COL0 | Matrix column 0 |
| D4 | GP6 | SDA | OLED I2C1 SDA |
| D5 | GP7 | SCL | OLED I2C1 SCL |
| D7 | GP1 | ENC_A | Encoder A |
| D8 | GP2 | ENC_B | Encoder B |
| D9 | GP4 | COL1 | Matrix column 1 |
| D10 | GP3 | COL2 | Matrix column 2 |
| 3V3 | | 3V3 | OLED VCC |
| GND | | GND | Common ground |

The matrix is 3 rows by 3 columns, with diodes `COL2ROW`. The encoder push switch is not wired. The firmware does not use D6.

## Build

Run this once from `Firmware/`:

```sh
ln -sfn "$PWD/qmk/keyboards/frostbite" ~/qmk_firmware/keyboards/frostbite
```

Then build both keymaps:

```sh
qmk lint -kb frostbite
qmk compile -kb frostbite -km default && cp ~/qmk_firmware/frostbite_default.uf2 ../production/firmware.uf2
qmk compile -kb frostbite -km bringup && cp ~/qmk_firmware/frostbite_bringup.uf2 ../production/bringup.uf2
```

`tests/run.sh` runs the desk tests. See `tests/README.md`.

## Flashing

1. Put the XIAO in its UF2 bootloader. There are three ways:
   - Hold the XIAO **BOOT** button while you plug in USB. Use this for the first flash, because the other two ways need Frostbite firmware on the XIAO.
   - Double-tap the XIAO **RESET** button.
   - Hold **Approve + Stop** (bottom-left and bottom-right keys) while you plug in USB. This also clears EEPROM. One key alone does nothing, so a stuck switch cannot enter the bootloader.
2. A drive named **RPI-RP2** appears.
3. Drag `firmware.uf2` or `bringup.uf2` onto it. The board reboots by itself.

## Bring-up

Flash `bringup.uf2` to check the hardware. It needs no host.

For the first 3 s after boot, every OLED pixel is on. Look for dead pixels or lines. Then the screen shows this:

```
BRINGUP  keys 3/9
seen 12..5....
key: r1 c1 Agent 5
knob: 4 CW
```

- **Keys**: press each key once. The count must reach `9/9` and `seen` must read `123456789`. A dot means that key has not been seen. The `key:` row names the last key and its matrix row and column. Keys send their fallback keycodes.
- **Knob**: turn it. Clockwise must read `CW` and the count must go up. The knob does not change the volume in this keymap.
- **OLED**: all four rows must be readable and the right way up.

If the text is upside down, comment out `#define FROSTBITE_OLED_FLIP` in `config.h` and rebuild.

Encoder settings are in `keyboard.json`. `encoder.rotary[0].resolution` is transitions per step.

- If one click moves `knob:` by two, double the value.
- If it takes two clicks to move `knob:` by one, set it to 2.
- If clockwise reads `CCW`, swap `pin_a` and `pin_b`. Do not resolder. `PCB/tools/check_netlist.py` and verify `G2.firmware_pins` both require `pin_a` on `ENC_A`, so update them too.

## Keymap

Key index is `row * 3 + col`, the order of `keys[]` in `design.json`.

| Key | Index | Matrix | Host mode (Raw HID) | Fallback keycode |
|---|---|---|---|---|
| Agent 1-6 | 0-5 | rows 0-1 | KEY n tap or hold, slot n | F13-F18 |
| Approve | 6 | (2,0) | KEY 6 | F19 |
| Talk | 7 | (2,1) | KEY 7 and F20, held while held | F20, held while held |
| Stop | 8 | (2,2) | KEY 8 | Escape |
| Encoder | | GP1, GP2 | Select slot 0-5 (wraps), ENCODER event | Volume up or down |

**Talk** always sends F20, so push-to-talk tools work with or without the host app. The host ignores its KEY event on purpose.

**Stop** in fallback is a plain Escape to the app in front. See `host/README.md`.

On macOS, F14 and F15 (Agent 2 and 3 in fallback) may change display brightness.

## Raw HID protocol

Usage page `0xFF60`, usage `0x61`, 32-byte reports. Byte 0 is the command. Unused bytes are zero. The descriptor has no report IDs. The OS consumes hidapi's leading `0x00` on writes, so the firmware sees the command first.

| Direction | Command | Bytes | Notes |
|---|---|---|---|
| host to device | `0x01` SET_SLOT | `[01, slot 0-5, status]` | |
| host to device | `0x02` SET_ALL | `[02, s0, s1, s2, s3, s4, s5]` | |
| host to device | `0x03` OLED_LINE | `[03, line 0-1, len, up to 21 ASCII bytes]` | `len = 0` restores the default text. A shorter string blanks the rest of the line, so the host need not pad. |
| host to device | `0x05` PING | `[05]` | Reply is `[05, 1, selected_slot]` |
| host to device | `0x06` SET_SELECTED | `[06, slot 0-5]` | |
| device to host | `0x81` KEY | `[81, key 0-8, action]` | Action 1 is tap, 2 is hold. Hold is sent once the key has been down 400 ms. A tap is sent on release if sooner. |
| device to host | `0x82` ENCODER | `[82, direction, selected_slot]` | Direction `01` is clockwise, `FF` is counter-clockwise. |

The firmware ignores any other command, including `0x04`. It does not reply and changes nothing.

| Status | Code | Word | Strip |
|---|---|---|---|
| idle | 0 | `IDLE` | `-` |
| run | 1 | `RUN` | `R` |
| done | 2 | `DONE` | `D` |
| needs | 3 | `WAIT` | `?` |
| error | 4 | `ERR` | `!` |

A status above 4 counts as idle.

## Host mode

Host mode lasts while a PING arrived in the last 5 s, so the host should PING every 1-2 s.

Without a PING the pad uses the fallback keycodes and the OLED shows the no-host screen. Fallback only changes what is shown. Statuses, OLED text and the selected slot are kept. The pad returns to the last host state when PINGs resume, with no USB reconnect. The host can send SET_ALL with every PING, because matching values change nothing.

## OLED

The OLED has four rows of 21 characters.

```
slot 3  DONE
2run 1wait 1done 1err
.....................
1R 2? 3D 4! 5- 6R HID
```

| Row | Host mode | Fallback |
|---|---|---|
| 1 | OLED_LINE 0, or `slot N  WORD` for the selected slot | `FROSTBITE   no host` |
| 2 | OLED_LINE 1, or a summary once statuses arrive, or a hint | `F13-F20 Esc  knob=vol` |
| 3 | Dotted divider | Dotted divider |
| 4 | Slot strip and `HID` | Slot strip, all idle, and `KBD` |

**Slot strip**: each slot shows its number and its status character from the table above. The strip is always visible, even when the host fills rows 1 and 2. The selected slot is inverted, so it reads as dark text on a lit block. Nothing is inverted in fallback.

**Divider**: do not write text to row 3. Blanking it every frame dirties that block and starves row 4 of QMK's one-block-per-loop render.

**Sleep**: the display turns off after 10 minutes without activity. Only a key, the encoder, a real status change or a USB resume counts. PING, OLED_LINE, SET_SELECTED and a repeated SET_ALL neither wake it nor keep it on, but text still updates for the next wake. A USB resume lights it once so a waiting prompt is visible, and the 10-minute timer runs from there.
