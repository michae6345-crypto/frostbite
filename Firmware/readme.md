# frostbite

qmk firmware for a 3x3 pad with an ec11 and a 0.91" oled on a xiao rp2040.

    ln -s "$PWD" ~/qmk_firmware/keyboards/frostbite
    qmk compile -kb frostbite -km default

Hold approve while plugging in to get to the bootloader, or double tap reset on the xiao.

| XIAO | GPIO | Net |
|---|---|---|
| D0 | GP26 | ROW0 |
| D1 | GP27 | ROW1 |
| D2 | GP28 | ROW2 |
| D3 | GP29 | COL0 |
| D4 | GP6 | SDA |
| D5 | GP7 | SCL |
| D7 | GP1 | ENC_A |
| D8 | GP2 | ENC_B |
| D9 | GP4 | COL1 |
| D10 | GP3 | COL2 |
