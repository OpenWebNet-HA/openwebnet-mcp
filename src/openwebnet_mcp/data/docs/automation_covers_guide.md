# Automation & Covers Platform Configuration (WHO = 2)

The automation platform (`cover.py`) manages motorized roller shutters, venetian blinds, motorized curtains, and garage doors.

## 🪟 Movement & Positioning Controls

### Basic Commands (WHAT)
- `*2*1*WHERE##`: Move UP (Open).
- `*2*2*WHERE##`: Move DOWN (Close).
- `*2*0*WHERE##`: STOP movement immediately.

### Advanced Multi-Parameter Commands
Modern installations and centralized controls emit parameterized movement frames:
- `*2*11#STEP#PRIORITY#SELECTOR*WHERE##`: Advanced UP (e.g. `*2*11#100#001#1*0##` to open all shutters to the 100% endpoint with priority 001).
- `*2*12#STEP#PRIORITY#SELECTOR*WHERE##`: Advanced DOWN (e.g. `*2*12#100#001#1*0##` to close all shutters to endpoint).
- `*2*10#PRIORITY#SELECTOR*WHERE##`: Advanced STOP (e.g. `*2*10#001#1*0##`).

### Position Status (Dimension 10, read-only)
Standard physical actuators measure opening duration or use calibrated run-times. Advanced actuators with absolute positioning (e.g. Legrand 067557) report their position through dimension 10 (`WHO_2.pdf` pp. 6-7, 19):
- Read frame: `*#2*WHERE*10##`
- Reply / event: `*#2*WHERE*10*<STATUS>*<LEVEL>*<PRIORITY>*<INFO>##`
  - `STATUS`: `10` stop, `11` up, `12` down, `13` step-by-step up, `14` step-by-step down.
  - `LEVEL`: `0` fully closed .. `100` fully open, `255` position unknown.
  - `INFO`: `0` normal, `12` PUL + disabled, `13` disabled, `14` command not executed, `15` PUL.
- There is no dimension 10 write.

### Go To Level (Dimension 11, write-only)
The only level write in the document (p. 20):
- Write frame: `*#2*WHERE*#11#<PRIORITY>*<LEVEL>##` (e.g. `*#2*21*#11#001*75##` moves cover 21 to 75 %).
- The gateway echoes `*#2*WHERE*#11#<PRIORITY>#<TYPE>*<LEVEL>##`, then dimension 10 frames and `*2*0*WHERE##` when the level is reached.
- There is no dimension 11 read and no tilt / slat / louvre angle dimension anywhere in `WHO_2.pdf`.

## 🎛️ Centralized Transmitters & Scope Covers

Centralized controls (such as BTicino **LN-4660M2**, **H4660M2**, **AM5860M2**, and Legrand **067558**) are input keypads without built-in relays or motor outputs:
- **General Scope Addressing**: When configured with `A=GEN`, they broadcast directly to `WHERE = 0` (General scope).
- **Dual-Function STOP / PRESET Button**:
  - While shutters are moving: pressing STOP emits `*2*10#001#1*0##`, halting all shutters.
  - While shutters are stationary: pressing the button activates the **PRESET** function to recall a pre-programmed intermediate level.
- **Home Assistant Behavior**:
  - Actuators respond individually with `DIMENSION 10` feedback reports (`*#2*21*10*...##`), allowing Home Assistant to discover and calibrate each motorized shutter.
  - Centralized button presses fire `myhome_general_automation_event` on the Home Assistant event bus and trigger native Device Triggers (*"Centralized shutter UP/DOWN/STOP"*).
  - A General Scope Cover (`MyHOMEScopeCover`) aggregates the collective state across all managed shutters.

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
      advanced: true
    all_shutters:
      where: "0"
      name: "All House Shutters"
```
