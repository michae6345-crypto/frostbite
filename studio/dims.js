(function (root) {
  const FB = root.FB = root.FB || {};
  // Real part dimensions, mm. Sources and confidence are in ../docs/DIMENSIONS.md.
  FB.dims = {
    pitch: 19.05,            // MX key spacing (0.75")
    switchCutout: 14.0,      // MX plate cutout (Cherry 0.551" ±0.002; Gateron housing 14.00 ±0.03)
    plateThickness: 1.5,     // MX clip thickness at the cutout (Cherry 0.06" ±0.004)
    pcbThickness: 1.6,       // JLCPCB default 2-layer
    switchHeightAbovePlate: 6.6,   // plate top -> top of switch HOUSING (not stem); 11.6 - 5.0
    switchHeightBelowPlate: 5.0,   // plate top -> housing bottom / PCB top (excludes 3.3 pins)
    capBottom: 18.2,         // DSA/XDA cap footprint (SP DSA 0.718" = 18.24)
    capTopDSA: 12.7,         // SP DSA top 0.5"
    capTopXDA: 15.9,         // XDA top ~16 (vendor-dependent)
    capHeightDSA: 7.6,       // generic DSA; SP spec 7.39, the taller value is the safe one
    capHeightXDA: 9.5,       // sources say 9.1–9.56, near the top of that range
    oledModule: { w: 38.0, h: 12.0, t: 3.6 },   // 0.91" I2C module board (38x12) incl. header end; t = board+glass+back parts, no header
    oledActive: { w: 22.4, h: 5.6 },            // 22.384 x 5.584 lit area
    ec11: { body: 12.0, shaftAbovePcb: 24.5, knobDiameter: 18.0 },  // body 11.7 x 12.0; L=20 shaft = 4.5 body + 20 -> tip 24.5 above PCB
    xiao: { w: 17.8, h: 21.0, t: 3.5 },        // Seeed wiki 21 x 17.8; t from retail listings (see tMax)
    sk6812MiniE: { w: 3.2, h: 2.8 },
    heatSetInsert: { od: 5.0, length: 4.0, holeDiameter: 4.7 },     // kit "M3x5x4" = M3, OD 5, L 4; hole per Hackpad guide
    m3Head: 5.5,             // ISO 4762 socket head dk max
    printTolerance: 0.3,     // per side, printed part <-> PCB / parts (Hackpad: 0.2–0.4)
    minWall: 2.0,            // structural FDM wall (>= 4-5 perimeters @0.4)

    switchHousingTop: 15.6,          // top-housing outline at plate (Cherry 15.6; Gateron KS-3 15.4), the larger value
    switchHousingBottom: 14.0,       // bottom housing through the cutout
    switchClipSpan: 14.9,            // across clip tips (Gateron 14.9 ±0.3)
    switchStemAboveHousing: 3.6,     // Cherry
    switchStemTopAbovePlate: 10.2,   // 11.6 + 3.6 - 5.0 (at rest)
    switchTravel: 4.0,
    switchPinLength: 3.3,            // contact pins below PCB-top seat
    switchCenterPostLength: 2.8,     // Gateron Ø3.85 post
    plateGapBelow: 3.5,              // plate underside -> PCB top (5.0 - 1.5)
    switchPins: {                    // MX footprint, magnitudes from switch centre; signs in ../docs/DIMENSIONS.md
      centerHole: 4.0, pegHole: 1.7, pinHole: 1.5,
      pin1x: 3.81, pin1y: 2.54,      // (-3.81, -2.54) KiCad coords, y down
      pin2x: 2.54, pin2y: 5.08,      // (+2.54, -5.08)
      pegX: 5.08                     // (±5.08, 0) PCB-mount plastic pegs (5-pin switches)
    },
    capRimAbovePlate: 6.0,           // estimate: cap skirt bottom at rest
    capTopAbovePlateDSA: 13.6,       // estimate: rim + capHeightDSA
    capTopAbovePlateXDA: 15.5,       // estimate: rim + capHeightXDA

    oledGlass: { w: 30.0, h: 11.5, t: 1.45 },  // panel glass outline (UG-2832 type)
    oledGlassInset: 3.5,             // glass starts this far from the board end opposite the header
    oledHeader: { pins: 4, pitch: 2.54, fromEnd: 1.5, spacer: 2.5 }, // pin row 1.5 from board end; std header plastic 2.5
    oledGlassTopAbovePcb: 5.2,       // on a std 2.5 header: 2.5 + ~1.2 board + 1.45 glass (≈ plate top level)

    ec11Detail: {
      bodyW: 11.7, bodyD: 12.0, bodyH: 4.5,      // metal frame + switch, above PCB
      bushingDiameter: 7.0, bushingHeight: 7.0,   // plain Ø7 bushing (no thread) on EC11E
      shaftDiameter: 6.0, shaftFlat: 4.5, flatLength: 10.0, // D-cut: 4.5 across flat; flat 10 long on switch versions
      shaftL1Short: 15, shaftL1: 20, shaftL1Long: 25,       // shaft length options measured from body top
      pinPitch: 2.5, switchPinSpacing: 5.0, pinRowSpacing: 14.5, pinHole: 1.0,
      lugOuterSpan: 12.5, pinLength: 3.5, pushTravel: 0.5
    },
    knobTypical: { dMin: 15, dMax: 20, height: 15, boreDepth: 12 },  // aftermarket knobs for 6 mm D shaft (typical)

    xiaoDetail: { pinPitch: 2.54, rowSpacing: 15.24, pinsPerSide: 7, tMax: 4.5 },
    xiaoUsbC: { w: 9.0, h: 3.3, overhang: 1.4 },   // receptacle; overhang past the XIAO board edge
    usbPlugRelief: { w: 13.0, h: 8.0 },            // wall opening for a typical USB-C cable overmold

    sk6812Detail: { t: 1.78, leadSpan: 5.88, lensBelowLeads: 0.94, holeW: 3.4, holeH: 3.0 }, // reverse-mount PCB hole (body 3.2x2.8 + clearance)

    heatSetHoleDepth: 4.0,           // Hackpad guide: Ø4.7 x 4 deep
    heatSetBossOd: 8.0,              // 4.7 hole + 2 x ~1.6 wall (ruthex min wall 1.3)
    m3Clearance: 3.4,                // Hackpad guide: screw pass-through
    m3SelfTap: 2.9,                  // Hackpad guide: screw straight into plastic
    m3HeadHeight: 3.0,
    m3Counterbore: 6.0,              // head 5.5 + clearance
    m3ScrewLength: 16
  };
  if (typeof module !== "undefined" && module.exports) module.exports = FB.dims;
})(typeof window !== "undefined" ? window : globalThis);
