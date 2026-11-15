# Climate & Thermoregulation Configuration (WHO = 4)

The climate platform (`climate.py`) interfaces with BTicino MyHOME thermoregulation central units (3550 4-zone or 99-zone), standalone thermostats (L/N/NT4691), and temperature probe sensors (3475).

## 🌡️ Architecture & Dimensions

### Temperature Readings (Dimension 0)
- Measured temperature is reported in tenths of a degree Celsius (4 digits, zero-padded):
  - `*#4*1*0*0215##` -> Zone 1 temperature is 21.5°C.

### Target Setpoint & Mode (Dimension 14)
- Setting the target temperature requires the temperature (tenths of a degree, `0050`..`0400`, in 0.5 °C steps) and the target mode (`WHO_4.pdf` pp. 8, 23):
  - Format: `*#4*#Z*#14*<TEMP>*<MODE>##` on a zone via the central unit, `*#4*#0*#14*<TEMP>*<MODE>##` on the central unit.
  - Mode `1`: Heating
  - Mode `2`: Cooling (conditioning)
  - Mode `3`: Generic
  - Example: `*#4*#1*#14*0210*1##` -> Set Zone 1 target to 21.0°C in Heating mode.
  - Standalone thermostats without a central unit (live F461, MyHomeServer1 plants) take the bare zone instead: `*#4*1*#14*0210*1##` (not in the document; five of the thirteen emulated gateways NACK it).
- Anti-freeze is not a mode value of dimension 14: it is the WHAT 102 command (`*4*102*#Z##`, p. 10), thermal protection WHAT 202 (p. 11), OFF WHAT 303 (p. 10) and the automatic weekly program WHAT 311 (p. 9).

### Local Offset (Dimension 13)
- The dial / knob offset of a physical room thermostat is read with dimension 13 (`*#4*Z*13*OL##`, p. 17): `00` knob at 0, `01` / `02` / `03` = +1 / +2 / +3 °C, `11` / `12` / `13` = -1 / -2 / -3 °C, `4` local OFF, `5` local protection. It is read-only; `*4*40*Z##` releases the local adjustment (p. 13).
- Dimension 22 is **not** the offset: it is the split air-conditioner control on `3#Z#N` (pp. 66-68) and non-actuator dimension 22 frames (`*#4*Z*22##`, `*#4*#0*22##`, `*#4*0*22##`, `*#4*Z*#22*...##`) crash the thermoregulation daemon on 10 of 13 emulated gateways (and rebooted a live F461 `2.0.11`); OWNd (#136) refuses to send any WHO 4 dimension 22 frame as a safety guard.

## 📋 YAML Configuration Example

```yaml
myhome:
  climates:
    living_room_zone:
      zone: 1
      name: "Living Room HVAC"
      heat_support: true
      cool_support: true
    bedroom_zone:
      zone: 2
      name: "Master Bedroom HVAC"
      heat_support: true
      cool_support: false
```
