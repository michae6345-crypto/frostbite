# Hackpad rules audit

Frostbite checked against Hack Club's published Hackpad requirements and real gallery builds, on 2026-11-03,
at commit `d58ec31`. Design files were not changed.

**Result: see the counts at the end of section 1.** The items that need a decision first:

1. **The submission route may be gone.** The old form is closed and points to Stardance, and Stardance ended on
   1 November (item A1).
2. **Three page rules fail:** no BOM CSV in the repo root, no "why I made this" in the README, and the README appears
   to be AI-written, which the Stardance page lists as not allowed (items C11, D7, D8).

## Sources

All pages were read on 2026-11-03 in the built-in browser, except where a GitHub path is given.

| Source | Status |
|---|---|
| hackpad.hackclub.com `/guide`, `/parts`, `/submitting`, `/faq`, `/resources`, `/add-components`, `/gallery`, `/` | Read in full |
| hackpad.hackclub.com `/assembly` | Read, but it is an unfinished stub. Steps stop mid-sentence, and `website/src/pages/hackpad/Assembly.md` is cut off the same way |
| `forms.hackclub.com/hackpad` | Read. Closed, one line of text |
| `forms.hackclub.com/hackpad-submission` | 404, although the Stardance guide links to it |
| stardance.hackclub.com `/missions/hackpad`, `/missions/hackpad/guide` (all 5 steps), `/resources/*` (14 guides) | Read as a signed-out guest. Project pages and forms were not seen |
| `github.com/hackclub/hackpad`, branch `clean` | The default branch. Its text matches the live site |
| `github.com/hackclub/hackpad`, branch `main` | Last changed 2026-03-20. Older text that the live site no longer shows |
| `github.com/hackclub/stardance` | Source for the ship and funding checks |
| printlegion.hackclub.com | Read in full |

**Quoting.** `hackclub/hackpad` is MIT licensed, so its text is quoted exactly. GitHub reports no licence for
`hackclub/stardance`, so it is paraphrased with a page or `file:line` pointer, apart from one short quote at D8.
Gallery repos are other builders' own writing, so they are paraphrased the same way. This is narrower than "quote everything", on purpose. Open the pointer for the exact wording.

**Which rules count.** Live hackpad.hackclub.com pages and live Stardance pages are current. Text only on the `main`
branch, in `deprecated/`, or in the old PR template is **legacy**: section 1E lists it separately and it is never
scored as a FAIL.

## 1. Requirements checklist

Evidence comes from this repo unless stated. "Re-run" means I ran the tool myself rather than reading stored results.

### A. Program and logistics

| ID | Requirement and source | Status | Evidence |
|---|---|---|---|
| A1 | Somewhere to submit. `/submitting`: "you can fill out the project submission form!" | UNCLEAR | **Blocker.** The form page says it is closed and sends you to stardance.hackclub.com. Stardance ships closed at noon ET on 2026-11-01 (`config/initializers/constants.rb:14`; tooltip in `app/models/project.rb`). Commit `85e9a0f` (#1595, 2 Nov) blocks new projects too, but the live footer still showed build `48351d72`, which predates it, and the mission page still shows "Create a project". The design-funding button and controller have no closed check in the source. So a design submission may still work, but nothing confirms it. Ask in #hackpad |
| A2 | `/submitting`: "You can only do hackpad once! If you already got a hackpad kit, you're not eligible to get a second" | UNCLEAR | Only the user can confirm |
| A3 | Stardance eligibility: age 13-18 (landing FAQ, `_faq.html.erb`), identity verified and YSWS eligible (`project.rb` ship checks) | UNCLEAR | Account facts, not visible from here |
| A4 | `/submitting`: "You'll need to make a post to get feedback on your project, so don't forget this step!" (#hackpad-ships) | UNCLEAR | No evidence of a post. Not posted as part of this audit |
| A5 | Stardance time tracking and devlogs: Lapse or a markdown journal, at least one devlog (`/resources/hardware`, `/resources/starting-hardware`, `project.rb`) | UNCLEAR | No journal or devlog in the repo. Stardance account not visible |
| A6 | Feedback from other people on the design (`/resources/shipping-hardware`, step 5) | UNCLEAR | No record in the repo |
| A7 | `/submitting`: "make sure all your files are committed on GitHub!" | PASS | `gh api`: repo public, remote head `d58ec31` equals local head, working tree clean |
| A8 | Stardance project fields: root repo URL, README URL, description, screenshot banner, AI declaration (`project.rb` ship checks) | UNCLEAR | Stardance project not visible. Repo URL is ready |

### B. Hardware

| ID | Requirement and source | Status | Evidence |
|---|---|---|---|
| B1 | `/parts`: "Your PCB is smaller or equal to 100mmx100mm" | PASS | Edge.Cuts parsed from `PCB/frostbite.kicad_pcb`: 61.15 × 83.15 mm |
| B2 | `/parts`: "The PCB only uses 2 layers" | PASS | Only F.Cu and B.Cu are copper layers. `production/gerbers.zip` has only F_Cu and B_Cu |
| B3 | `/parts`: "Your case fits within 200x200x100mm (length / width / height)" | PASS | STL bounds re-measured: Top 75.15 × 97.15 × 16.0, Bottom 75.15 × 97.61 × 9.91, GlowBand 74.15 × 96.15 × 8.8, Knob 18 × 17.9 × 15. `CAD/README.md` gives 75.2 × 98.9 × 49.5 assembled with caps |
| B4 | `/parts`: "Your case only has 3D printed parts, no acrylic or laser cut parts" | PASS | `CAD/README.md` lists four printed parts and no others |
| B5 | `/faq`, on other microcontrollers: "Unfortunately not for hackpad!" | PASS | U1 is the XIAO RP2040 |
| B6 | `/parts`: "You're allowed to use other parts, but you'll have to source them yourself on your on money." | PASS | Board has U1, 9 SW, 9 D, 1 ENC, 1 J, 13 LED, all inside kit counts. Extras (6 frosted caps, knob, clear PETG) are listed as bought in `README.md` and `docs/BOM.md` |
| B7 | Input limit: **no live rule** (see the finding below) | PASS | 9 switches + 1 encoder = 10 inputs, which clears every old limit too |
| B8 | `/submitting`: "You should be running DRC in KiCAD, and you should see 0 errors." | PASS | Re-run with kicad-cli 10.0.8: 0 errors, 0 unconnected, 0 parity issues, 26 warnings (21 silk_over_copper, 5 silk_edge_clearance). Warnings are allowed: "It's OK to have some warnings, especially about the silkscreen!" ERC re-run: 0 |
| B9 | `/resources`: "don't use Edge.Cuts - use the M3 mounting hole footprint!" | PASS | The PCB has no mounting holes, it sits on the bosses. The Edge.Cuts LED openings come from the care-package footprint |
| B10 | `/resources`: "There's 19.05mm gap between the center of each switch" | PASS | SW1, SW2 and rows in `design.json`: 19.05 mm pitch |
| B11 | `/add-components`: "If you're using 4+ keys, you should use matrix wiring!" | PASS | 3×3 matrix with 9 1N4148 |
| B12 | `/add-components`: "I would recommend using Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal" | PASS | That exact footprint is used |
| B13 | `/add-components`: "I would recommend using the symbol RotaryEncoder_Switch and the footprint RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm" | PASS | Uses the `_CircularMountingHoles` variant (Ø2.6 round, against the plain footprint's 2.8 × 1.5 oval). A recommendation, not a rule, and ByteBoard used the same variant |
| B14 | `/add-components`: "make sure your symbol and both footprint both say SK6812MINI-E" and "Make sure your pinout matches the following screenshot _exactly:_" | PASS | Per-key LEDs. Symbol `SK6812MINI-E`, footprint `SK6812MINI-E_key`. Pads match the page screenshot: 1 VCC top-left, 2 DOUT bottom-left, 3 GND bottom-right, 4 DIN top-right. Nets match on all 9 |
| B15 | Same rule, for the 4 lens-down glow LEDs | UNCLEAR | `SK6812MINI-E_glow_down` is a custom mirrored footprint. The name and nets fit, but no Hack Club page covers mounting a MINI-E lens-down, and I found no gallery build that does it. Whether the leads seat on the pads needs a real part |
| B16 | `/parts`: "the pin order is GND-VCC-SCL-SDA, MAKE SURE YOUR PCB MATCHES" | PASS | J1 pins 1-4 run GND, +3V3, SCL, SDA top to bottom, header at the right end of the module. That is Hack Club's `oled.png` rotated 180° and matches the footprint used by Stratum, froskeys, Mediapad and Matyas |
| B17 | `/submitting`: "I recommend leaving about 0.2mm between any two parts that may touch." `/resources`: "Use a 0.2mm gap between 3D printed parts" | PASS | PCB pocket 0.3 per side (`design.json` `case.tolerance`), USB tongue gap 0.2 (`frostbite_case.py:109`), band inset 0.5. The tutorial's example uses 0.4 per side, "plus 0.4mm on each side to account for printing tolerances", so 0.3 is tighter than that example but above the stated rule |
| B18 | `/resources`: "if you're using heatset inserts, make a 4.7mm diameter hole, 4mm deep" | PASS | `CAD/frostbite_case.py:60` |
| B19 | `/resources`: "if you just want the screw to pass through without threading, use a 3.4mm diameter hole." | PASS | `CAD/frostbite_case.py:61` |
| B20 | USB-C cutout in the case (Stardance guide, step 3 checklist) | PASS | 13.5 × 8 window in `design.json`, centred on the receptacle, `CAD/README.md` |

**Finding on "fewer than 16 inputs": refuted as a Submission-page rule.** The live `/submitting` and `/parts` pages
contain no input limit. The wording exists in two places the live site does not show:

- `main` branch, `website/src/pages/hackpad/Submission.mdx:36`: "You have less than 16 inputs (switches, encoders, etc)"
- `clean` branch, `website/src/pages/hackpad/deprecated/Submit_blueprint.md:35`, same text, not routed in `main.tsx`

The closest live statement is only a kit count: "16x MX-Style switches" and "2x EC11E Rotary encoders". Frostbite is
unaffected, but these should stop citing it as a current rule: `docs/VERIFICATION.md:25`, `README.md:212`,
`verify/README.md:37`, `verify/fbverify/checks.py:245`, `studio/verify/run.js:503`.

### C. Files and structure

| ID | Requirement and source | Status | Evidence |
|---|---|---|---|
| C1 | `/submitting`: "CAD: This should contain a single file containing your ENTIRE hackpad." and "This should include the PCB (a blank rectangle is okay!)" | PASS | `CAD/frostbite-assembly.step` is the only model in `CAD/`. It holds 95 solids, including PCB, switches, caps, OLED, XIAO, EC11, LEDs. The other files are the generating source, which Stardance's shipping page says it would ideally like too |
| C2 | `/submitting`: "This includes the .kicad_pro, .kicad_sch, and .kicad_pcb file" | PASS | All three in `PCB/` |
| C3 | `/submitting`: "Original firmware for your macropad. QMK, KMK, ZMK, etc derivatives are valid!" | PASS | Custom QMK keyboard and keymaps in `Firmware/qmk/keyboards/frostbite/` |
| C4 | Folder names CAD, PCB, Firmware (`/submitting`), "create a folder called "production"" | PASS | Exact, including case: `CAD/`, `PCB/`, `Firmware/`, `production/` |
| C5 | `/submitting`: "In total, you should have 3 folders in your project folder." and "Everything should match exactly, except for the filenames." | UNCLEAR | Eight top-level folders plus `design.json`: the four expected, plus `docs/`, `host/`, `studio/`, `verify/`. Literally this does not match. Approved repos do the same (section 2): Hack Club's own example adds `assets/`, and Mediapad adds `Companion/`, the closest match to `host/`. Likely fine. Only a reviewer can confirm |
| C6 | `/submitting`: "The end file you get should be named gerbers.zip and contain all the production files in it." | PASS | 14 files: all copper, mask, silk, paste, edge and drill layers at the zip root |
| C7 | `/submitting`: "Top.STEP", "Bottom.STEP", "Middle.STEP", one file per part. Stardance guide step 1 says STEP rather than STL | PASS | `Top.step`, `Bottom.step`, `GlowBand.step`, `Knob.step`. The lower-case extension is fine: filenames are exempt, and Stratum and Matyas use `.step` |
| C8 | `/submitting`: "for QMK the resulting file should be named firmware.uf2" | PASS | `production/firmware.uf2`: every block has the UF2 magic, RP2040 family `0xe48bff56`, 87,552 bytes. `led-test.uf2` is an extra |
| C9 | Firmware compiles (Stardance guide checklist) | PASS | `verify/evidence/G6.compile_default.json` is PASS. Not recompiled here, because the harness writes into `verify/` |
| C10 | Printing Legion asks requesters for the STL files | PASS | Four `.stl` files in `production/` |
| C11 | BOM as a CSV in the repo root, with links, USD prices and shipping (`/resources/shipping-hardware`, step 5) | **FAIL** | No CSV in the root. The only tracked CSV is `PCB/build/frostbite-pos.csv`. `README.md` and `docs/BOM.md` have no links, prices or shipping. Enforcement looks loose: Stratum and CubeShifter have no root CSV, but Hack-Piano does, and GD-Hackpad has `Not_Required_BOM.csv`. The kit `/submitting` page asks only for "a BOM for your parts" in the README |
| C12 | Open source: the Stardance landing FAQ says projects count as long as they are open source (`_faq.html.erb`) | UNCLEAR | The repo is public but has no LICENSE file, while orpheuspad, Mediapad, Matyas, SplashPad and froskeys do. No page names a LICENSE file as a requirement |

### D. README and originality

| ID | Requirement and source | Status | Evidence |
|---|---|---|---|
| D1 | `/submitting`: "A screenshot of your overall hackpad" | PASS | `CAD/previews/assembly-iso.svg.png`. The hero at the top is an AI concept image, labelled as such. The Stardance README guide prefers a photo, then a render, so the real render would be better as the hero |
| D2 | `/submitting`: "A screenshot of your schematic" | PASS | `PCB/images/schematic.png` |
| D3 | `/submitting`: "A screenshot of your PCB" | PASS | `PCB/images/pcb_render_top.png`, `pcb_render_bottom.png` |
| D4 | `/submitting`: "A screenshot of your case and how it'll fit together" | PASS | `CAD/previews/exploded-iso.svg.png`, `docs/images/exploded.png` |
| D5 | `/submitting`: "a BOM for your parts" | PASS | `## BOM` in `README.md` |
| D6 | What it is and how it is used (`/resources/shipping-hardware`, step 5) | PASS | README intro and Features |
| D7 | A couple of sentences on why you made it (same page) | **FAIL** | The README says what it does but never why. Only the Credits section mentions inspiration |
| D8 | Must not have "AI Generated READMEs" (`/resources/shipping-hardware`, step 5) | **FAIL** | The only commit carries `Co-Authored-By: Claude Opus 5.5`, and `docs/VERIFICATION.md` describes agents building the project. This reads as an AI-written README. If the user wrote it, change this to PASS. The user's "AI is OK" does not cover this line, see section 4 |
| D9 | No work that isn't your own or copied from projects (same page) | UNCLEAR | Layout ideas are credited in `README.md`. Own design and firmware, but AI-built, so judged under the "should feel like your own work" tooltip |
| D10 | AI usage declared on the project (`project.rb:873-876`, `show.html.erb:318`) | UNCLEAR | Required field on Stardance. Not visible from here. See section 4 |
| D11 | No missing firmware (same page) | PASS | `Firmware/` and `production/firmware.uf2` |

### E. Legacy rules, not on any live page

These can still shape what a reviewer expects, but no live page states them.

| ID | Requirement and source | Status | Evidence |
|---|---|---|---|
| E1 | `main` `Tutorial.mdx:157`: "Put the name of your hackpad on any silkscreen of your PCB." and write "XIAO HERE" | PASS | "FROSTBITE" on F.SilkS and B.SilkS, "XIAO HERE" on B.SilkS |
| E2 | `main` `Tutorial.mdx:340`: "Next, we will brand our case!" Old PR template: "I HAVE BRANDED ALL MY PARTS (PCB, CASE) WITH MY HACKPAD'S NAME" | UNCLEAR | **No name on the case.** `CAD/frostbite_case.py` makes no text. `docs/VERIFICATION.md:28` says "name on a hidden face", which was never built, and its cited source (Submission page, FAQ) does not say this. A small debossed name would close it |
| E3 | Old PR template: "I HAVE MADE SURE MY 3D PRINTED PARTS DO NOT REQUIRE SUPPORTS" | PASS | My STL scan: GlowBand has no overhang over 45°. Bottom's 69 mm² and Knob's 24.5 mm² are small flat roofs (counterbores, bore end). Top has 42 mm², which I read as chamfers |
| E4 | Old PR template: tolerances "(0.25mm)" | PASS | 0.3 per side at the PCB |
| E5 | Old PR template: "I DO NOT HAVE MORE THAN 16X SWITCHES, 2X ROTARY ENCODERS, 1X OLED, 16X LEDS." | PASS | 9, 1, 1, 13 |
| E6 | Old PR template: "A few sentences about the inspiration and challenges" | UNCLEAR | Same gap as D7 |
| E7 | `main` `Tutorial.mdx:139`: "have the head of the XIAO poking out of the Edge.Cuts rectangle" | PASS | XIAO flush with the edge, receptacle overhangs about 1.4 mm (`design.json` `mcu.usb`) |

### Counts

| | PASS | FAIL | UNCLEAR |
|---|---:|---:|---:|
| A Program | 1 | 0 | 7 |
| B Hardware | 19 | 0 | 1 |
| C Files | 9 | 1 | 2 |
| D README | 7 | 2 | 2 |
| E Legacy | 5 | 0 | 2 |
| **Total (58)** | **41** | **3** | **14** |

**Not due yet.** Stardance's build stage also asks for a public demo video, physical build devlogs and a photo of the
build in the README. Those apply after the kit arrives and are not scored.

### Corrections needed in our own docs

| File | Says | Origin |
|---|---|---|
| `docs/VERIFICATION.md:25` (and four others, above) | Inputs < 16, from the Submission page | Not on the live page |
| `docs/VERIFICATION.md:27` | Silkscreen name and "XIAO HERE", from Submission page, tutorial | Only in `main` `Tutorial.mdx`. Not live |
| `docs/VERIFICATION.md:28` | Case name on a hidden face, from Submission page, FAQ | Only in `main` `Tutorial.mdx`, and not built |
| `docs/VERIFICATION.md:22` | USB head past Edge.Cuts, from submission page, tutorial | Only in `main` `Tutorial.mdx`. Not live |
| `docs/VERIFICATION.md:4` | "$15 grant" for the PCB | `/submitting` now says "$10 Card grant" for the PCB and "$5 Card grant" for the print. Stardance lists $10 for the PCB and $8 shipping credit for a print under 300 grams |

## 2. Comparison with example and gallery repos

Clones in the scratchpad `refs/` folder, read only. Nothing in them was run.

| Repo | CAD folder | PCB folder | Firmware folder | Production folder | Extra top level | BOM |
|---|---|---|---|---|---|---|
| **Frostbite** | `CAD` | `PCB` | `Firmware` | `production` | `docs`, `host`, `studio`, `verify`, `design.json` | README + `docs/BOM.md` |
| orpheuspad (the reference) | `cad` | `pcb` | `firmware` | `production` | `assets`, LICENSE | README |
| stratum-macropad (Stardance) | `cad` | `pcb` | `firmware` | `production` | `assets` | README |
| mediapad (Stardance) | `CAD` | `PCB` | `Firmware` | `Production` | `Companion`, `irl_assets`, LICENSE | README + `PCB/BOM.csv` |
| froskeys | `cad` | `pcb` | `firmware` | `production` | root images, `JOURNAL.md`, `yapping.md` | README |
| ByteBoard | `CAD` | `PCB` | `Firmware` | `Production` | none | README |
| Matyas-s-Hackpad | `CAD` | `PCB` | `Firmware` | `Production` | `Assets`, LICENSE | README |
| SplashPad | `CAD` | `PCB` | `Firmware` | `Production` | `BOM.md`, LICENSE | `BOM.md` |
| chinnyyys-hackpad | `CAD` | `PCB` | `FIRMWARE` | none | none | none found |

- **Case-sensitive names are not enforced.** Hack Club's own example uses lower-case `cad/pcb/firmware`, and approved
  repos mix `Production/` with `production/`. Frostbite follows the `/submitting` text exactly, which is the safest choice.
- **Filenames are free in practice.** `Top part.step`, `macropad-stratum-top.step`, `main body.stl`, `Gerbers.zip` and
  `Firmware.uf2` all appear in gallery repos. The only hard names are the ones Frostbite already uses.
- **Extra folders are normal.** Every repo above except ByteBoard and chinnyyys adds something at the top level.
  `Companion/` in Mediapad holds a companion app, as `host/` does here. Other gallery repos add `backend/`, `Trash/` and
  `assets/`. Frostbite has more extra folders than any of them, so the README's "Repo layout" table is worth keeping.
- **The example breaks the "3 folders" sentence itself.** The `/submitting` tree image shows `assets`, `cad`, `firmware`,
  `pcb`, `production`.
- **More than one model in `CAD/` has been approved.** chinnyyys has four STEP files and SplashPad has many. Frostbite is stricter.
- **What approved repos have that Frostbite lacks:** a real build photo and a demo video (build stage only), a LICENSE
  file (item C12), and a KiCanvas badge, which the shipping guide suggests.

## 3. Lessons from real builds

Paraphrased from each repo. Commit dates come from `gh api`, since the local clones are shallow.

| # | What went wrong | Source | Frostbite exposure | Evidence and action |
|---|---|---|---|---|
| 1 | Hackpad ended before the builder submitted, so the project moved to the next program | froskeys `JOURNAL.md`, 16 Aug entry | **Yes, now** | Item A1. Ask in #hackpad this week. Froskeys shows a design can move to a later hardware program |
| 2 | First-time solderer could not fit the LEDs and pulled up a trace, so the build shipped with no RGB | Gallery text for DynamicWhiteHat | **Yes, high** | 13 hand-soldered SK6812s, against ByteBoard's 8. Pads are 0.82 × 1.25 mm, shorter than the care package's 1.6, to clear the cut-out. Signal necks are 0.2 mm. Three spare LEDs. `CAD/README.md` has no LED soldering advice. Practise on scrap and add a short note |
| 3 | Encoder soldered on the wrong side, then a leg snapped off during removal. Only the spare in the kit saved it | Matyas `README.md:59` | **Yes** | `CAD/README.md` step 2 says "Solder the bottom-side parts" and lists diodes, EC11 and OLED, all of which sit on the **top** side (J1, ENC1 on F.Cu). This wording invites that exact mistake. Fix the sentence |
| 4 | LED footprint error left a build with no working LEDs, fixed only in later gerbers | GD-Hackpad `README.md:35`, 27 Sep commits | **Partly** | Key LED pad map checked (B14). The modified footprints and lens-down glow LEDs have no build history (B15). PCB is ordered once |
| 5 | Firmware compiled but was unproven on hardware, then replaced with corrected files about a month later | Stratum `README.md:54`, 24 Aug commits | **Yes** | Frostbite is compile-only too. `led-test.uf2` covers bring-up, and Stardance accepts untested firmware at design stage. Stratum's `config.h` also had to override wrong board I²C defaults; Frostbite sets GP6/GP7 in `config.h` |
| 6 | After bring-up the builder fixed the encoder, changed its direction and the SK6812 order, and switched to Seeed pin numbers | froskeys commits, 26-28 Sep 2025 | **Low** | Pin map re-checked: U1 pads match `design.json`, including the mirrored underside (D0 at top right seen from above). Encoder direction is a one-line firmware fix |
| 7 | Prints did not fit first time. Screw sizes and the OLED position were corrected, then the case and PCB revised | Mediapad commits, 19 and 28 Aug | **Low in CAD, unproven in plastic** | Case is generated from `design.json`, and OLED window lines up with the module (x 6-36 against the panel at 6-35.5). Real prints are still untested |
| 8 | LED grid sat about half a key pitch off the switch grid, so an LED could not single out one key | Mediapad `README.md`, Help browser | **No** | Each key has its own LED at the key's x, y + 5.08 (SW1 11.525, 33.525; LED1 11.525, 38.605), on the side away from the switch pins |
| 9 | Diode soldered backwards, no tools to fix it. Encoder button never worked. USB port position regretted | TheSeagullDev `README.md:39` | **Some** | 9 diodes; band direction is in `docs/BOM.md`. Encoder push is deliberately unwired and stated in the README. USB is at the back edge |
| 10 | LED power rework. The schematic diff adds +5V symbols and two diodes around the LEDs | SplashPad commit `acddf8f`, "LED Voltage Fix" | **Yes, known** | The commit does not explain itself, so the cause is unconfirmed. Frostbite runs LEDs at 5 V with 3.3 V data, flagged in `README.md`. Bring-up test decides. Only the first LED sees 3.3 V data |
| 11 | Cases remade or reprinted, and measurements were the regret | ByteBoard, jampad `README.md`, imperial-audio-modulator `README.md:20` | **Yes** | Frostbite goes to a stranger's printer once. `CAD/README.md` advises a test print of the cutouts, which Printing Legion doesn't obviously allow for. Item below |
| 12 | Board came out too wide, so it was split and stacked | Hack-Piano `README.md:33` | **No** | 61.15 × 83.15 mm |
| 13 | No heat-set inserts, so the case self-threads | Stratum `README.md` | **No** | Four inserts, per `/resources` |

**Printing Legion risk.** Its page says to post STLs, a picture and your country, then ask a printer and pay shipping from
the grant. It promises no material. Frostbite's look depends on iced PETG and a clear PETG band in two materials, so
ask the printer first. SplashPad's BOM simply asks for a colour. Weight is fine: about 92 g if solid, under the 300 g
Stardance mentions.

## 4. AI use: what the pages say

- **hackpad.hackclub.com:** nothing. No live page, and no file on the `clean` branch, mentions AI, in either direction.
- **Stardance shipping page:** `/resources/shipping-hardware`, step 5, lists "AI Generated READMEs" among things your
  project must not have. Source: `app/views/guides/topics/hardware/shipping-hardware.md`. This is the only line on any
  page about AI in a hardware project, and it covers the README specifically, so the user's general OK does not settle it.
- **Stardance project page:** declaring AI use is a required ship check. You write how you used it, or "None". The
  tooltip says AI use is fine as long as the result feels like your own work (`app/models/project.rb:873-876`,
  `app/views/projects/show.html.erb:318`). So disclosure belongs in that field. No page asks for it in the README.
- **Image scan:** `app/services/ai_image_detector.rb` flags uploads containing C2PA AI-media markers, shown to admins.
  All 11 `docs/renders/*.png` carry that marker with an OpenAI manifest, including the README hero. The README label
  is honest, but don't use these as the Stardance banner or in devlogs.
- **Not applicable:** `AI_POLICY.md` in `hackclub/stardance` governs pull requests to the Stardance platform, not
  submitted projects. Its ban on AI media should not be read as a project rule.

**Where Frostbite stands.** The README discloses only the concept renders. It says nothing about AI help on the PCB,
case, firmware or host code. Precedent: Mediapad's README openly says its firmware was mostly AI-written, and it is in
the gallery. Suggested actions: rewrite the README in the user's own words, fill the declaration fully, and consider a
one-line note in the README like Mediapad's.
