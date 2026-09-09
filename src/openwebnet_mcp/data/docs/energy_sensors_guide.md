# Energy Management & Power Meters Guide (WHO = 18)

The energy management subsystem (`sensor.py`) captures electricity, water, and gas metrics from BTicino power meters (such as F520, F521, F522, F523, and 3523).

## ⚡ Measured Dimensions

- **Instantaneous Active Power (Dimension 1)**: Current power load in Watts.
  - Query: `*#18*WHERE*1##`
  - Response: `*#18*WHERE*1*<WATTS>##` (e.g. `*#18*1*1*2350##` = 2350 W).
- **Hourly Totalizer (Dimension 2)**: Accumulated Wh in the current hour.
- **Daily Totalizer (Dimension 3)**: Accumulated Wh for the current day.
- **Monthly Totalizer (Dimension 4)**: Accumulated Wh for the current month.
- **Lifetime Accumulated Totalizer (Dimension 11)**: Cumulative total energy in Wh.

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
