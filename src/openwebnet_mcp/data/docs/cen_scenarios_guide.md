# CEN & CEN+ Scenario Pushbuttons Guide (WHO = 15, WHO = 25)

CEN and CEN+ scenario pushbuttons are physical wall switches configured to emit control signals rather than directly switching a load. They allow physical keypresses to trigger advanced automations, scenes, and integrations in Home Assistant.

## 🔘 CEN (WHO = 15) vs CEN+ (WHO = 25)

| Feature | CEN (WHO = 15) | CEN+ (WHO = 25) |
|---|---|---|
| Addressing | `WHERE#BUTTON` (buttons 1..32) | `WHERE` + button in parameter (buttons 1..255) |
| Short Press | WHAT = 1 (`*15*1*WHERE#B##`) | WHAT = 21 (`*25*21#B*WHERE##`) |
| Start of Long Press | WHAT = 0 (`*15*0*WHERE#B##`) | WHAT = 22 (`*25*22#B*WHERE##`) |
| Long Press Heartbeat | WHAT = 3 (`*15*3*WHERE#B##`) | WHAT = 23 (`*25*23#B*WHERE##`) |
| Release After Hold | WHAT = 2 (`*15*2*WHERE#B##`) | WHAT = 24 (`*25*24#B*WHERE##`) |
| Dry Contact States | N/A | WHAT = 31 (closed) / 32 (opened) |

## 🪄 Home Assistant Blueprint Integration

The Home Assistant community maintains the official **MyHome CEN+ Commands Blueprint** (`community.home-assistant.io/t/myhome-cen-commands/260345`).
When configured, button events fire `myhome_cen_event` on the event bus:
```yaml
trigger:
  - platform: event
    event_type: myhome_cen_event
    event_data:
      where: "11"
      button: 2
      action: "short_press"
action:
  - service: light.toggle
    target:
      entity_id: light.living_room_ceiling
```
