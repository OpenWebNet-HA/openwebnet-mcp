# CEN & CEN+ Scenario Pushbuttons Guide (WHO = 15, WHO = 25)

CEN and CEN+ scenario pushbuttons are physical wall switches configured to emit control signals rather than directly switching a load. They allow physical keypresses to trigger advanced automations, scenes, and integrations in Home Assistant.

## 🔘 CEN (WHO = 15) vs CEN+ (WHO = 25)

| Feature | CEN (WHO = 15) | CEN+ (WHO = 25) |
|---|---|---|
| Button | WHAT = button `00..31` (leading zero significant) | WHAT parameter (`#B`) |
| Source (`WHERE`) | Source address; never the button (`#3` riser, `#4#I` local bus) | Virtual object |
| Pressure / short press | `*15*B*WHERE##` (start of *every* press) | `*25*21#B*WHERE##` (whole short press, no release frame) |
| Release after short press | `*15*B#1*WHERE##` | — (CEN+ sends none) |
| Start of long press | first `*15*B#3*WHERE##` | `*25*22#B*WHERE##` |
| Long press heartbeat (~0.5 s) | repeated `*15*B#3*WHERE##` | `*25*23#B*WHERE##` |
| Release after long press | `*15*B#2*WHERE##` | `*25*24#B*WHERE##` |

Examples from the [OpenWebNet Encyclopedia](https://github.com/OpenWebNet-HA/OpenWebNet-Encyclopedia/blob/305278651b593a785271c7c4df15d9e802a41ffb/functional/who-15-cen/README.md): `*15*01*0001##`, `*15*02*22##`, `*15*06*36#4#01##`. A short CEN press is `*15*02*22##` then `*15*02#1*22##`; a long press is `*15*02*22##`, one or more `*15*02#3*22##`, then `*15*02#2*22##`.
| Dry Contact States | N/A | WHAT = 31 (closed) / 32 (opened) |

## 🪄 Home Assistant Blueprint Integration

The Home Assistant community maintains the official **MyHome CEN+ Commands Blueprint** (`community.home-assistant.io/t/myhome-cen-commands/260345`).
MyHOME fires `myhome_cen_event` (WHO 15) and `myhome_cenplus_event` (WHO 25) with `object`, `pushbutton`, `event` and `where`. For a CEN toggle, trigger on the short *release*: `pushbutton_short_press` also fires at the start of every long press.
```yaml
trigger:
  - platform: event
    event_type: myhome_cen_event
    event_data:
      object: 22
      pushbutton: 2
      event: "pushbutton_short_release"
action:
  - service: light.toggle
    target:
      entity_id: light.living_room_ceiling
```
