# Frostbite firmware audit

QMK tree `f5db962110` (2026-10-29). Nothing here ran on hardware. Evidence comes from QMK source, the built ELF, reference boards, fetched datasheets, and a host harness.

**Harness.** `#include`s the real `keymaps/default/keymap.c`, links the real `drivers/oled/oled_driver.c` and lib8tion C paths, and adds a fake clock plus an SSD1306 GDDRAM model behind stubbed I2C. Built with clang ASan and UBSan. Files are in `/private/tmp/claude-501/-Users-tripi-Documents-frostbite/c28e1ea7-1ef6-4d14-b065-e25be6b901fb/scratchpad/audit/`: `harness.c`, `panel.c`, `h_ledtest.c`, `proto_test.py`, outputs `harness.out`, `harness_fix.out`, `ledtest.out`, `proto.out`. Results: 0 harness failures, 23/23 protocol checks.

## Summary

| Severity | Count | Findings |
|---|---:|---|
| BLOCKER | 1 | F1 |
| MAJOR | 6 | F2 to F7 |
| MINOR | 5 | F8 to F12 |

| ID | Sev | Status | Finding |
|---|---|---|---|
| F1 | BLOCKER | CONFIRMED | Slot strip and most of the divider never reach the panel |
| F2 | MAJOR | LIKELY | OLED is upside down in the shipped UF2 |
| F3 | MAJOR | CONFIRMED | Pad shows idle after a PING gap without USB reconnect |
| F4 | MAJOR | CONFIRMED | Burn-in sleep never fires while the daemon shows `N ago` |
| F5 | MAJOR | CONFIRMED | Host opens any `0xFF60` device; PING and SET_SELECTED are VIA write commands |
| F6 | MAJOR | UNVERIFIED | Encoder needs two clicks per step if the part is a true 30/15 EC11E |
| F7 | MAJOR | UNVERIFIED | XOSC startup delay is 1/64 of Seeed's XIAO value |
| F8 | MINOR | CONFIRMED | Fallback fade is 300 ms for agent LEDs, not 1500 ms |
| F9 | MINOR | CONFIRMED | OLED stays dark after a long host sleep if nothing changed |
| F10 | MINOR | CONFIRMED | `max_brightness` does nothing for our LEDs; the limiter is the real guard |
| F11 | MINOR | CONFIRMED | 49.7-day timer wrap gives a brief false host mode |
| F12 | MINOR | UNVERIFIED | `tap_code` volume has no delay; F14/F15 may hit macOS brightness |

`production/firmware.uf2` and `production/led-test.uf2` are byte-identical to fresh builds (`differing bytes 0`), so the firmware findings below apply to the UF2s in `production/`.

---

## Findings

### F1. BLOCKER, CONFIRMED: slot strip never reaches the panel

`keymap.c:490-492` blanks text row 2 and redraws the dots on every `oled_task_user` call:

```c
oled_write_P(PSTR("                     "), false);
for (uint8_t x = 0; x < 126; x += 3) oled_write_pixel(x, 19, true);
```

Each frame the spaces erase the dots and the pixels restore them. `oled_write_char` (`oled_driver.c:617-622`) and `oled_write_pixel` (`:699-702`) each compare against the old byte, so both mark the block dirty even though the net result is unchanged.

`oled_render_dirty` resets `update_start = 0` on every call (`oled_driver.c:455`) and sends the lowest dirty block. It stops after `OLED_UPDATE_PROCESS_LIMIT`, which defaults to 1 (`oled_driver.h:308-309`). `keyboard.c:754` runs `oled_task()` every main loop, with no update interval on a non-split board (`oled_driver.h:304`). Block 8 is therefore re-dirtied and re-sent forever, and blocks 9 to 15 starve.

Harness result, simulated panel 3 s after boot and in host mode:

```
page2 buffer |~~~~~~~~~~~~~~~~~~~~~| panel |#####################| bytes differing=96 never-written=96
page3 buffer |1- 2- 3- 4- 5- 6- KBD| panel |#####################| bytes differing=128 never-written=128
blocks sent: 1 1 1 1 1 1 1 1 2992 0 0 0 0 0 0 0
...
page3 buffer |1R 2? 3D 4! 5- 6R HID| panel |#####################| bytes differing=128 never-written=128
```

Consequences:
- Row 4 (slot strip, selected slot, HID/KBD) never appears. Rows 1 and 2 are correct.
- Page 3 and most of page 2 keep power-on GDDRAM. Mediapad's `config.h` describes this exact look for unsent RAM ("speckle or dots").
- I2C runs nonstop: `idle KBD screen: 42000 I2C bytes, 2000 transactions in 1000 loops`. That is about 945 µs of bus time per loop (42 bytes × 9 bits at 400 kHz, `chibios_config.h:61-62`).
- If the bus hangs, each failed render can stall up to `OLED_I2C_TIMEOUT` = 100 ms. That is from source; I did not simulate it.
- At the 10-minute sleep, the render path calls `oled_on()` (`oled_driver.c:453`) while dirty blocks drain, so the panel toggles: `display toggles in 30 ms=15`. Rendering a dirty block is the only route that writes the starved blocks, so the strip reaches the panel only as it goes dark.

Tried to disprove:
- The run uses QMK's real driver unmodified, so this is not a model of its behaviour.
- Control: `ledtest` has no pixel writes and shows all four rows.
- Fix test: deleting only `keymap.c:491` in a scratch copy gives `bytes differing=0` on all four pages, `0 I2C bytes` at idle, and 1 display toggle at sleep. Nothing else writes page 2, so drawing the dots alone is enough.

### F2. MAJOR, LIKELY: OLED upside down by default

`FROSTBITE_OLED_FLIP` is commented out (`config.h:28`), so the build uses `OLED_ROTATION_0`.

Our J1 is at the right end of the module, pins GND/VCC/SCL/SDA top to bottom, on F.Cu (`PCB/frostbite.kicad_pcb` pads at x=39.0, y=9.19 to 16.81). Parsed PCB files show the same arrangement on these Hack Club boards, all with rotation 0 and pad 1 = GND at the top right:

| Board | Firmware setting |
|---|---|
| Stratum | `OLED_ROTATION_180` (`stratum.c:295-296`) |
| Mediapad | `OLED_ROTATION_180` (`keymaps/lixtheyt/keymap.c:518-519`) |
| Matyas | `OLED_ROTATION_180` (`keymaps/default/keymap.c:27-28`) |
| Froskeys | `flip=True` (`firmware/code.py:36`) |

The Froskeys build photo (`irl.jpg`) shows "Froskeys" upright with the header at the reader's right. On Mediapad and Matyas the OLED sits above the switches (lower PCB y), as on Frostbite; on Stratum it sits above the encoder. ByteBoard has the same footprint, but its `Firmware/main.py` has no OLED code, so it offers no counterexample.

Not CONFIRMED because no Frostbite module has been fitted. The ledtest bring-up settles it. Fix: define `FROSTBITE_OLED_FLIP` by default, otherwise reflash is needed after first assembly.

### F3. MAJOR, CONFIRMED: pad stays idle after a PING gap without USB reconnect

`housekeeping_task_user` clears statuses, `host_line` and glow on fallback (`keymap.c:320-327`). `Daemon.push` sends only values that differ from `_sent` (`daemon.py:54-73`), and `_sent` clears only on `"connected"` (`daemon.py:121-124`). `PingReply` is ignored (`daemon.py:132-133`), and the reply carries nothing that would reveal a reset.

Real firmware and real `Daemon`, with `proto_test.py`:

```
firmware after 6 s without PING: [0, 0, 0, 0, 0, 0] '' (127, 227, 255, 70) hm 0
daemon sent after PING resumed: ["OLED_LINE 1 '6s ago               '"]
firmware now: [0, 0, 0, 0, 0, 0] '' '6s ago               ' (127, 227, 255, 70) hm 1  board statuses: [1, 0, 0, 0, 0, 0]
```

The host believes slot 0 is RUN while the pad shows idle until that value next changes. A Mac sleep is the likely trigger if the HID handle stays open across sleep. That part is UNVERIFIED; any stall over 5 s is confirmed to do it. During USB suspend QMK stays in the `protocol_pre_task` loop, so the clear runs on resume.

Fix: clear `_sent` when the link has seen a gap over 5 s, or resend full state periodically.

### F4. MAJOR, CONFIRMED: burn-in sleep never fires while the daemon runs

Any changed `OLED_LINE` calls `wake()` (`keymap.c:278-281`). The daemon's line 1 for an occupied slot is `{ago} ago` (`state.py:264-270`), and `tick()` runs at 1 Hz (`daemon.py:190-191`). The text changes at least once a minute.

```
OLED_LINE changes sent in 15 min: 68  OLED off seconds: 0  of 900
control: OLED went off after 593 s
```

The README's 10-minute protection works only with no occupied slot selected. Fix: do not wake on OLED_LINE, or wake only on status change.

### F5. MAJOR, CONFIRMED: host can drive another QMK keyboard with VIA writes

`HidTransport.find` matches only usage page and usage (`device.py:299-302`); nothing filters VID/PID. `0xFF60/0x61` is the default for every QMK Raw HID board. VIA command IDs (`quantum/via.h:59-60`):

- `0x05 id_dynamic_keymap_set_keycode`, the same byte as our PING. An all-zero payload sets layer 0, row 0, col 0 to `KC_NO` (`via.c:404-406`), and the daemon repeats it every 2 s.
- `0x06 id_dynamic_keymap_reset`, the same byte as our SET_SELECTED.

If a VIA keyboard enumerates first, the daemon writes to its keymap. This needs a second such keyboard attached. I read the source but did not run it against one. Fix: also require VID `0xFEED` and PID `0x4642`.

### F6. MAJOR, UNVERIFIED: encoder may need two clicks per step

`keyboard.json:30` sets `"resolution": 4`, four transitions per event. `design.json` and `docs/BOM.md` name an "Alps EC11E". Alps' page for EC11E15244G1 lists "Number of detent: 30" and "Number of pulse: 15", which is two transitions per detent. A search snippet of a Chipdip EC11 document (not opened) lists other EC11E variants at 2:1 too.

Model using QMK's LUT verbatim: `res 4 events after 10 detents (2 transitions each): 5  res 2: 10`. At four transitions per detent, resolution 4 gives 10 events.

Against this, Stratum and Mediapad keep resolution 4 with the kit encoder, but neither states the behaviour, and the kit part number is unknown. Settle with ledtest: if `knob:` moves once per two clicks, set resolution 2.

Direction is also open. QMK reports clockwise=true when A leads B (LUT trace). `ENC_A` goes to pad A and `ENC_B` to pad B. I found no EC11E statement of which leads, only an RS search snippet (not opened) for an EC11B saying A leads on CW. Ledtest settles this too.

### F7. MAJOR, UNVERIFIED: XOSC startup delay shorter than Seeed specifies

Seeed's board header (`lib/pico-sdk/src/boards/include/boards/seeed_xiao_rp2040.h:18-20`):

```c
// On some samples, the xosc can take longer to stabilize than is usual
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
```

QMK does not use that header, and the default is 1. Disassembly of our `xosc_init` shows `movs r2, #47` written to STARTUP, about 1 ms, against 3008. If the crystal is late, `pll_init` spins on lock with no timeout (`pll.c:65`). A hang on cold plug is my inference from that loop; I have not seen it happen.

22 keyboards or platform files in the tree set this. Stratum and Mediapad do not, so the risk is sample-dependent. Settle by cold-plugging about 20 times, but the one-line fix is cheap: `#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64` in `config.h`. `cornifi` sets it in `config.h` and its built `xosc_init` loads 3008, so that path works. Building ours with the define also gives 3008.

### F8. MINOR, CONFIRMED: fallback fade overridden

`keymap.c:322` starts a 1500 ms fade, then `:330` restarts it with `FADE_MS` in the same call.

```
fade ms agent LED0=300 (FALLBACK_FADE_MS=1500, FADE_MS=300) glow LED9=1500
```

### F9. MINOR, CONFIRMED: OLED dark after long host sleep

`suspend_power_down_user` turns the OLED off, and there is no `suspend_wakeup_init_user`. After resume, `last_activity` is stale:

```
suspend: active during=0; after 11.6 min host sleep, resume, 50 ms later oled_active=0
```

It wakes on the next key, turn, or changed message. `suspend_power_down_user` is also redundant, because `quantum.c:520-522` already calls `oled_off()`.

### F10. MINOR, CONFIRMED: `max_brightness` does not protect anything here

`RGB_MATRIX_MAXIMUM_BRIGHTNESS` is used only in `rgb_matrix.c:638` (sethsv). `rgb_matrix_set_color` goes straight to the driver. Current is held by our limiter alone, which works: forcing every key down, all statuses, and glow `#ffffff` at 255 gave `max post-limit channel sum=3943 budget=3978`. That is 15.6 full-channel equivalents, about 187 mA at the datasheet's 12 mA version, plus up to 13 mA IDD. Not a defect, but the `keyboard.json` value is misleading.

### F11. MINOR, CONFIRMED: 49.7-day wrap

`host_mode()` has no bound beyond `timer_elapsed32`. If `ever_pinged` is set and the pad stays powered with no PING for 2^32 ms, elapsed wraps and host mode turns on for 5 s (`elapsed wrapped to 1 host_mode=1`). Keys are swallowed in that window. The OLED similarly relights for 10 minutes (same arithmetic at `keymap.c:452`, read, not run).

### F12. MINOR, UNVERIFIED: two host-side key behaviours

- `tap_code(KC_VOLU)` has no delay (`keymap.c:240`), while QMK's default handler uses `tap_code_delay(KC_VOLU, 10)` (`quantum/encoder.c:161,169`). Mediapad also uses plain `tap_code`, with no reported issue. Settle by turning the knob quickly on the Mac.
- F14 and F15 (Agent 2 and 3 in fallback) may adjust display brightness on macOS. That is from memory, not verified. Settle by pressing them with no host app running.

---

## Verified passes

**Config**
- I2C1: `i2c_init` disassembly writes IO_BANK0 `+0x34`/`+0x3C` (GP6, GP7) with FUNC 3, and pads `0x5B` (input enabled, pull-up, 4 mA). `I2CD1.i2c = I2C1` (`hal_i2c_lld.c:404`), and only `I2CD1` is in the ELF. Seeed's header agrees (I2C1, SDA 6, SCL 7). `halconf.h` and `mcuconf.h` enable it; `i2c_lld_start` linked.
- Clock 400 kHz. `oled_buffer` is 0x200 bytes, so 128×32. OLED init runs after the 500 ms double-tap wait, and charge pump is enabled.
- Pins match `design.json`, the PCB U1 netlist, and Seeed's map. Diode pad 1 (K) is on the row, so COL2ROW is correct. Debounce defaults to 5 ms.
- `ws2812_flush`/`ws2812_init` linked from the vendor PIO driver. Datasheet (Opsco SK6812MINI-E Rev 04, fetched from akizukidenshi.com) gives bit order "G7 - G6 - ...... ..B0", and QMK defaults to GRB. RGB, not RGBW. QMK defaults fit its table:

| Param | QMK | Datasheet |
|---|---|---|
| T0H | 350 ns | 200 to 400 |
| T0L | 900 ns | ≥800 |
| T1H | 900 ns | 580 to 1000 |
| T1L | 350 ns | ≥200 |
| Period | 1250 ns | ≥1200 |
| Reset | 280 µs | >80 |

- Double-tap: `__late_init` is in the ELF. Bootmagic: `bootmagic_should_reset` is strong (`T`) over the weak default, reads both bits of row 2 after two debounced scans, and works with this matrix.
- Raw HID: 32-byte report, descriptor usage matches `config.h`, `send_raw_hid` length check passes (`bad raw_hid_send lengths: 0`).
- Flash: QMK defaults to W25Q080 stage2 (`docs/platformdev_rp2040.md:132-136`), the same choice as Seeed's header. EEPROM erase base in the ELF is `0xFF << 13` = 0x1FE000, the last 8 KiB of 2 MiB, which matches `PICO_FLASH_SIZE_BYTES` in Seeed's header. Binary is 43,688 bytes.

**RGB matrix**
- `keyboard.json` order matches `design.json` `keys[].led`. The PCB chain LED1 to LED13 runs DOUT to DIN in that order, and each LED sits at switch + (0, 5.08). `key_led` agrees. Coordinates scale correctly.
- `rgb_matrix_task` calls indicators once per frame when FLUSHING and only if effect ≠ 0 (`rgb_matrix.c:420-427`). `rgb_matrix_set_color` has no index remapping. Solid color at val 0 is a working black canvas; val 0 does not disable the effect.
- Timeout is 0, so no input-based LED sleep. `RGB_MATRIX_SLEEP` is defined, so LEDs go dark on USB suspend and return on resume.
- First boot: `RGB_MATRIX_DEFAULT_ON` true, and `keyboard_post_init_user` forces enable, mode and HSV with `_noeeprom`, so RGB does not start off and no runtime EEPROM writes occur.

**Keymap logic (harness, ASan and UBSan)**
- Tap at 399 ms and hold at 400 ms are exact, including across 16-bit and 32-bit timer wrap.
- F20 and agent keys keep matched edges across host-mode changes in both directions, so no stuck key.
- Host mode is on at +4999 ms and off at +5000 ms. Encoder wraps both ways. Fallback encoder sends volume and leaves the slot alone.
- 3,000,000 random packets with lengths 0 to 32: no sanitizer reports, invariants held. `len=255` truncates to 21, line > 1 and slot > 5 are ignored, status > 4 becomes idle.
- All 15,625 status combinations fit 21 chars after compaction. Selected is never dimmer than unselected at any ms. Error toggles every 500 ms.

**Stack and blocking**
- Largest frames: `rgb_matrix_indicators_user` 96 B, `oled_task_user` 72 B, `oled_render_dirty` 64 B, against a 0x800 process stack. I read frame sizes only and did not compute a full call-graph depth.
- `raw_hid_send` can block up to 100 ms once if the host is not draining, then `timed_out` makes later sends immediate until a TX completes (`usb_driver.c:267`, `:198`). Buffer depth is 4.
- The roughly 1 ms loop from F1 should not miss input: debounce is 5 ms, and a fast 4 rev/s on a 30-detent part is about 240 edges/s, or 4.2 ms apart (arithmetic, not measured). No runtime EEPROM writes come from our `_noeeprom` calls.

**Protocol**
- All host and device messages match byte for byte between `keymap.c`, `device.py` and `design.json`: 23/23, every key index, unused bytes zero, encoder `01`/`FF`, PING reply `[05, 01, sel]`.

**ledtest**
- With no key events: `0R 0G 0B 0W 1R ... 12W` then wraps, one LED lit per frame (`frames with >1 lit=0`), OLED `LED TEST 13/13` / `colour: white`, all four panel rows correct.
- No key handling is needed for it to run. If the OLED is missing, `oled_init` fails and `oled_task` returns early (`oled_driver.c:924`).
- It does not prove colour order or chain integrity on real parts; that is what the eye check is for.

**Not firmware, noted only:** datasheet VIH is 0.7×VDD, so 3.5 V at 5 V against 3.3 V data. `design.json` already flags this; Mediapad and Stratum use the same drive and photos show Mediapad's LEDs working.

## Fix order

1. F1: delete `keymap.c:491`.
2. F2 and F7: enable both defines in `config.h`.
3. F5: add VID/PID filter in `device.py`.
4. F3 and F4: decide the resend and wake rules.
5. Flash ledtest with OLED fitted to settle F2 and F6, then rebuild both UF2s.

## Sources

- [SK6812MINI-E datasheet](https://akizukidenshi.com/goodsaffix/sk6812mini-e.pdf)
- [Alps EC11E15244G1](https://tech.alpsalpine.com/e/products/detail/EC11E15244G1/)
- [QMK encoders doc](https://docs.qmk.fm/features/encoders)
