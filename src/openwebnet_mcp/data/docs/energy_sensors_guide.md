# Energy Management & Power Meters Guide (WHO = 18)

The energy management subsystem (`sensor.py`) captures electricity, water, and gas metrics from BTicino power meters (such as F520, F521, F522, F523, and 3523).

## ⚡ Measured Dimensions

WHERE is `5N` for a meter (F520 / F523 / 3522, N = 1..255), `7N#0` for an Energy Management actuator and `1N` for a Stop&Go (WHO_18.pdf; Encyclopedia who-18-energy-management/addressing.md).

- **Active Power (Dimension 113)**: current load in Watts.
  - Query: `*#18*WHERE*113##`
  - Response: `*#18*WHERE*113*<WATTS>##` (e.g. `*#18*51*113*2350##` = 2350 W).
- **Energy/Unit Totalizer (Dimension 51)**: the all-time totalizer (`*#18*WHERE*51*<VAL>##`; the document labels its unit Watt).
- **Monthly Totalizer (Dimension 52)**: `*#18*WHERE*52#Y#M##` -> `*#18*WHERE*52#Y#M*<VAL>##` (Y = yy).
- **Partial Totalizers (Dimensions 53, 54)**: current month and current day.
- **Actuator Totalizers (Dimension 72)**: `*#18*7N#0*72#<Tot_N>##` -> `Energy*D*M*Y*H*m`, Energy in Wh since the last reset (`*18*75#<Tot_N>*7N#0##`).
- **Historical series (Dimensions 511..514)**: started by WHAT `57#M#D`, `58#M`, `59#M`, `510#M`; the values arrive as `*#18*WHERE*511#M#D*Tag*Val##` (tags 1..24 hourly, 25 daily total).
- **Automatic updates**: `*#18*WHERE*#1200#1*<Time>##` (Time in minutes, 0 stops); the pushes are dimension 113 frames.

The earlier guide dimensions 1..4 and 11 (instantaneous power, hourly / daily / monthly / lifetime totalizers) are not in WHO_18.pdf nor in the Encyclopedia.

## 📊 Home Assistant Energy Dashboard Integration

The MyHOME integration automatically configures energy sensors with:
- `device_class: power` / `unit_of_measurement: W` for instantaneous load.
- `device_class: energy` / `state_class: total_increasing` / `unit_of_measurement: kWh` for cumulative totalizers.

```yaml
myhome:
  sensors:
    main_power_meter:
      where: "1"
      name: "Main Grid Power Meter"
      type: "power"
```
