# Climate & Thermoregulation Configuration (WHO = 4)

The climate platform (`climate.py`) interfaces with BTicino MyHOME thermoregulation central units (3550 4-zone or 99-zone), standalone thermostats (L/N/NT4691), and temperature probe sensors (3475).

## 🌡️ Architecture & Dimensions

### Temperature Readings (Dimension 0)
- Measured temperature is reported in tenths of a degree Celsius (4 digits, zero-padded):
  - `*#4*1*0*0215##` -> Zone 1 temperature is 21.5°C.

### Target Setpoint & Mode (Dimension 14)
- Setting target temperature requires specifying the temperature (tenths of a degree) and the target mode:
  - Format: `*#4*WHERE*#14*<TEMP>*<MODE>##`
  - Mode `1`: Heating
  - Mode `2`: Cooling
  - Mode `3`: Generic / Antifreeze
  - Example: `*#4*1*#14*0210*1##` -> Set Zone 1 target to 21.0°C in Heating mode.

### Local Offset (Dimension 22)
- Dial / knob offsets on physical room thermostats (-3°C to +3°C) are reported via dimension 22.

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
