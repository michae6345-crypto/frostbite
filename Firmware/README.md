# Frostbite firmware (QMK)

QMK keyboard definition for Frostbite 9: Seeed XIAO RP2040, 3x3 keys, EC11 encoder,
0.91" 128x32 SSD1306 OLED and 13 SK6812 MINI-E LEDs. `../design.json` is the source of truth.

```
qmk/keyboards/frostbite/
  keyboard.json          pins, matrix, encoder, WS2812 (PIO) on GP0, RGB matrix layout, USB IDs
  config.h               I2C1 on GP6/GP7, OLED 128x32 @ 0x3C, double-tap reset, hold time
  halconf.h, mcuconf.h   enable ChibiOS I2C1
  frostbite.c            two-key bootmagic, optional OLED flip
  keymaps/default/       Raw HID agent dashboard + keyboard fallback  -> production/firmware.uf2
  keymaps/ledtest/       LED chain / OLED bring-up test               -> production/led-test.uf2
```

USB VID/PID are **test values**: `0xFEED` / `0x4642`.

## Build

```sh
export PATH="$HOME/.local/bin:$HOME/Library/Application Support/qmk/bin:$PATH"
ln -sfn "$PWD/qmk/keyboards/frostbite" ~/qmk_firmware/keyboards/frostbite   # once; run from Firmware/
qmk lint    -kb frostbite
qmk compile -kb frostbite -km default    # -> ~/qmk_firmware/frostbite_default.uf2
qmk compile -kb frostbite -km ledtest    # -> ~/qmk_firmware/frostbite_ledtest.uf2
cp ~/qmk_firmware/frostbite_default.uf2 ../production/firmware.uf2
cp ~/qmk_firmware/frostbite_ledtest.uf2 ../production/led-test.uf2
```

## Flash

1. Put the XIAO into the UF2 bootloader:
   - double-tap the XIAO **RESET** button, or
   - hold the XIAO **BOOT** button while plugging in USB, or
   - **bootmagic combo**: hold **Approve + Stop** (bottom-left and bottom-right keys) while
     plugging in. This also clears EEPROM.
2. A drive named **RPI-RP2** appears. Drag `firmware.uf2` (or `led-test.uf2`) onto it.
   The board reboots by itself.

Bring-up order: flash `led-test.uf2` first, before soldering switches. Each LED lights
red, green, blue and then white in chain order while the OLED shows `LED TEST n/13`.
If LED n works but n+1 never lights, check LED n's DOUT, LED n+1's DIN, and its 5 V/GND.
The test build also shows the last key pressed (`key: rR cC`) and an encoder count.
If the OLED text is upside down, uncomment `#define FROSTBITE_OLED_FLIP` in `config.h` and rebuild.

## Keymap

Key index = `row * 3 + col` (design.json `keys[]` order). LED = the per-key LED index.

| Key | Index | Matrix | LED | Host mode (Raw HID)     | Fallback keycode    |
|-----|-------|--------|-----|-------------------------|---------------------|
| Agent 1 | 0 | (0,0) | 0 | KEY 0 tap/hold, slot 0 | F13 |
| Agent 2 | 1 | (0,1) | 1 | KEY 1, slot 1 | F14 |
| Agent 3 | 2 | (0,2) | 2 | KEY 2, slot 2 | F15 |
| Agent 4 | 3 | (1,0) | 5 | KEY 3, slot 3 | F16 |
| Agent 5 | 4 | (1,1) | 4 | KEY 4, slot 4 | F17 |
| Agent 6 | 5 | (1,2) | 3 | KEY 5, slot 5 | F18 |
| Approve | 6 | (2,0) | 6 | KEY 6 | F19 |
| Talk    | 7 | (2,1) | 7 | KEY 7 **and** F20 held while held (always) | F20, held while held |
| Stop    | 8 | (2,2) | 8 | KEY 8 | Escape |
| Encoder | - | GP1/GP2 | - | select slot 0-5 (wraps), ENCODER event | Volume up / down |

Glow LEDs 9-12 sit at the four corners. They show the SET_GLOW colour, which defaults to ice blue `#7fe3ff` at about 27 % brightness.

## Raw HID protocol (design.json `protocol`)

Usage page `0xFF60`, usage `0x61`, 32-byte reports. Byte 0 is the command and unused bytes are zero.

| Dir | Cmd | Bytes | Notes |
|-----|-----|-------|-------|
| host->dev | `0x01` SET_SLOT | `[01, slot, status]` | status: 0 idle, 1 run, 2 done, 3 needs, 4 error |
| host->dev | `0x02` SET_ALL | `[02, s0..s5]` | |
| host->dev | `0x03` OLED_LINE | `[03, line 0-1, len, <=21 ASCII]` | `len = 0` clears the line, so the default text returns |
| host->dev | `0x04` SET_GLOW | `[04, r, g, b, brightness]` | |
| host->dev | `0x05` PING | `[05]` | reply `[05, 1, selected_slot]` |
| host->dev | `0x06` SET_SELECTED | `[06, slot 0-5]` | |
| dev->host | `0x81` KEY | `[81, key 0-8, 1 tap / 2 hold]` | hold is sent as soon as the key has been down for 400 ms. A tap is sent on release if the key was released sooner. |
| dev->host | `0x82` ENCODER | `[82, 01 cw / FF ccw, selected_slot]` | |

**Talk** always sends F20 (held while the key is held) in both modes, so push-to-talk tools work
whether or not the host app is running. In host mode it also sends its KEY event, and the host ignores that event on purpose.

**Report ID**: the raw HID descriptor has no report IDs. hidapi's leading `0x00` on writes is
consumed by the OS, so the firmware sees the command as the first byte.

**OLED_LINE padding**: a shorter string blanks the rest of the line on the device, so the host
does not have to pad (padding to 21 is harmless).

**Host mode** lasts while a PING arrived within the last 5 s, so the host should PING about every 1-2 s.
Without a PING the pad falls back to the keycodes above and the encoder sends volume. Agent LEDs fade to idle,
the host's OLED text and statuses are cleared, and glow returns to its default.

**LEDs**: idle is dim white, run is blue `#3d8bff`, done is green `#2fbf5b`, needs is a slow amber `#ffb020` pulse
(2.4 s) and error blinks red `#ff4d4f` (1 Hz). The selected slot is brighter and breathes gently. Command keys are dim
white and brighten while pressed. Colour changes cross-fade. A simple current limiter keeps the total LED output within USB power.

**OLED**:
- Row 1 shows OLED_LINE 0, or `slot N  STATUS` for the selected slot (N is 1-6 on screen).
- Row 2 shows OLED_LINE 1, or a summary such as `3 run 1 wait 2 done` once the host has sent statuses, or otherwise a hint.
- Row 4 is a slot strip (`1- 2R 3D 4? 5! 6-`), with the selected slot inverted and `HID` or `KBD` showing the mode.
- Burn-in protection: the display turns off after 10 minutes without activity. A key press, an encoder turn or a HID message that changes something wakes it. A repeated PING does not count.

## Bootloader combo

Hold **Approve + Stop** while plugging in. Double-tapping RESET on the XIAO also works, and so does holding BOOT while plugging in.
