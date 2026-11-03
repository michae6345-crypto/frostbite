# Frostbite 9

A 3x3 Hack Club Hackpad macropad for supervising coding agents: six agent-slot
keys with status LEDs, Approve / Talk / Stop, an EC11 encoder, a 128x32 OLED and
four underglow LEDs. Seeed XIAO RP2040.

* Keyboard Maintainer: Frostbite contributors
* Hardware Supported: Frostbite 9 PCB (Seeed XIAO RP2040)
* Hardware Availability: Hack Club Hackpad

Make example for this keyboard (after setting up your build environment):

    qmk compile -kb frostbite -km default

Flashing example for this keyboard:

    qmk flash -kb frostbite -km default

See the [build environment setup](https://docs.qmk.fm/#/getting_started_build_tools) and the [make instructions](https://docs.qmk.fm/#/getting_started_make_guide) for more information. Brand new to QMK? Start with our [Complete Newbs Guide](https://docs.qmk.fm/#/newbs).

## Bootloader

Enter the bootloader in 3 ways:

* **Bootmagic reset**: Hold down Approve (bottom-left) and Stop (bottom-right) together and plug in the USB cable.
* **Physical reset button**: Double-tap the RESET button on the XIAO RP2040, or hold BOOT while plugging in.
* **Keycode in layout**: There is no `QK_BOOT` key in the default keymap.
