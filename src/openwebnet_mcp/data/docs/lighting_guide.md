# Lighting Platform Configuration & Control (WHO = 1, WHO = 24)

The lighting platform (`light.py`) integrates BTicino/Legrand relay actuators (F411), dimmers (F418), DALI controllers (F429/F429G), and multi-bus routed light endpoints.

## 💡 Supported Features & Addressing

### OpenWebNet Addressing Schemes (`WHERE`)
- **Point-to-Point**: `A*PL` or `APL` (e.g. `12` = Area 1, Point-Light 2).
- **Area Broadcast**: `A` (e.g. `1` turns all lights in Area 1 ON/OFF).
- **Group Addressing**: `#G` (e.g. `#1` to `#255`).
- **General Broadcast**: `0` (affects all lighting actuators on the system).
- **Bus Routing**: `A*PL#4#bus` (e.g. `12#4#1` sends command to device 12 on private SCS bus 1 via an F422 interface).

### Dimmable Lights vs Relay Actuators
- Dimmers support dimming percentage (1-100%), stepped levels (10 levels, WHAT 2..10), and transition fade times.
- DALI gateways (F429) support tunable white color temperatures (2700K - 6500K) and RGBW color channels.

## 🎛️ Transitions & Stepped Dimming

When `transition` is requested in `light.turn_on` or `light.turn_off`:
- Direct OpenWebNet speed parameter: `*1*1#<speed>*WHERE##` (speed `1` = instant to `10` = slowest ramp).
- Alternatively, the software-emulated stepped dimming engine issues smooth micro-step adjustments to ensure consistent fades across older actuators that lack native hardware ramp timing.

## 📋 YAML Configuration Example

```yaml
myhome:
  lights:
    living_room_ceiling:
      where: "12"
      name: "Living Room Ceiling Light"
      dimmable: true
    kitchen_under_cabinet:
      where: "14"
      name: "Kitchen Under-Cabinet LED"
      dimmable: false
    garden_perimeter:
      where: "21#4#1"
      name: "Garden Perimeter Floodlight"
      dimmable: false
```
