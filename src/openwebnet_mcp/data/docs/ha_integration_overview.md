# Home Assistant MyHOME Integration Overview

The **MyHOME** integration provides modern asynchronous communication between Home Assistant and Legrand/BTicino MyHOME SCS bus systems via OpenWebNet IP gateways (e.g. F454, F452, MH200, MH200N, MH202, MyHOMEServer1) or serial interfaces.

## 🏛️ System Architecture

```
[ Home Assistant Core ]
         ▲
         │ (async_added_to_hass / state changes / service calls)
         ▼
[ custom_components/myhome ]
   ├── gateway.py          (Gateway lifecycle, reconnection, packet dispatch)
   ├── light.py            (MyHOMELight - dimming, transitions, DALI)
   ├── cover.py            (MyHOMECover - shutters, venetians, positioning)
   ├── climate.py          (MyHOMEClimate - zones, setpoints, offsets)
   ├── sensor.py           (MyHOMESensor - power, energy, temperature)
   ├── binary_sensor.py    (MyHOMEBinarySensor - PIR, dry contacts)
   ├── switch.py           (MyHOMESwitch - loads, relays, aux channels)
   ├── media_player.py     (MyHOMEMediaPlayer - sound diffusion, sources, volume)
   └── ownd/               (OpenWebNet Daemon - connection, frames, discovery)
         ▲
         │ OpenWebNet TCP Sessions (Port 20000)
         │  - Command Session (*99*0##): send commands & read dimensions
         │  - Event Session   (*99*1##): real-time SCS bus listener
         ▼
[ MyHOME IP Gateway (F454 / MH200N) ]
         ▲
         │ SCS 2-wire 27V DC Differential Bus
         ▼
[ Physical Actuators & Sensors ] (F411, F418, F429, 3550, F441, F520, etc.)
```

## ⚙️ Configuration & Setup

Modern versions of `myhome` support full UI configuration via Home Assistant Config Flow:
- **Host**: IP address or hostname of the OpenWebNet gateway (e.g. `192.168.1.35`).
- **Port**: TCP port, standard is `20000`.
- **Password**: OpenWebNet password (numeric PIN `12345` or HMAC SHA-256 password for modern firmware).
- **Auto-Discovery**: Devices announcing state changes on the SCS bus during initial setup are automatically detected and added to Home Assistant entity registries.

## 📡 Live Bus Monitoring & Raw Commands

The integration exposes dedicated tools for advanced automation and debugging:
1. **Service `myhome.send_packet`**: Send arbitrary OpenWebNet frames directly to the SCS bus:
   ```yaml
   service: myhome.send_packet
   data:
     gateway_id: "your_gateway_id"
     packet: "*1*1*12##"
   ```
2. **Bus Monitor Events**: Emits `myhome_bus_event` on the Home Assistant event bus containing the raw frame, parsed WHO, WHAT, and WHERE parameters.
