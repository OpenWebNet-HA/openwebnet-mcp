# Automation & Covers Platform Configuration (WHO = 2)

The automation platform (`cover.py`) manages motorized roller shutters, venetian blinds, motorized curtains, and garage doors.

## 🪟 Movement & Positioning Controls

### Basic Commands (WHAT)
- `*2*1*WHERE##`: Move UP (Open).
- `*2*2*WHERE##`: Move DOWN (Close).
- `*2*0*WHERE##`: STOP movement immediately.

### Percentage Positioning (Dimension 10)
Standard physical actuators measure opening duration or use calibrated run-times. Actuators supporting absolute positioning (e.g. Legrand 067557) accept direct percentage writes:
- Write frame: `*#2*WHERE*#10*<LEVEL>##`
- Level `0`: Shutter fully closed.
- Level `100`: Shutter fully open.

### Slat / Louvre Angle (Dimension 11)
For venetian blinds:
- Write frame: `*#2*WHERE*#11*<ANGLE>##`
- Angle range `0` to `100` degrees.

## 📋 YAML Configuration Example

```yaml
myhome:
  covers:
    living_room_shutter:
      where: "21"
      name: "Living Room Shutter"
      run_time: 22.5
    bedroom_venetian:
      where: "22"
      name: "Bedroom Venetian Blind"
      tilt_support: true
```
