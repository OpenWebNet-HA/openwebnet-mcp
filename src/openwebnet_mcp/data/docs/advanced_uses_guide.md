# Advanced Uses: Bus Monitoring & Custom Packet Routing

This guide covers advanced automation patterns, inter-bus routing, and raw packet handling using the MyHOME integration.

## 🛰️ Inter-Bus Routing (F422 Couplers)

Large installations partition devices across physical SCS buses (e.g., Local Light Bus, Local Automation Bus, Master Backbone Bus) connected via F422 interface modules:
- Routing frame syntax: `WHERE#4#bus_id`
- Example: `12#4#1` represents actuator `12` situated on private bus `1`.
- Dimensions can also be queried over routed buses: `*#1*12#4#1*1##`.

## 📡 Live Packet Interception & Event Scripts

You can build custom automations that react to raw OpenWebNet messages:
```yaml
automation:
  - alias: "Trigger Scene on Master Off"
    trigger:
      - platform: event
        event_type: myhome_bus_event
        event_data:
          who: 1
          what: 0
          where: "0"  # General OFF
    action:
      - service: notify.notify
        data:
          message: "All lights were turned off via physical master switch."
```
