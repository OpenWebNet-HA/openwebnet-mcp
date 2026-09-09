# OpenWebNet Protocol & WHO Specifications Archive

Welcome to the **OpenWebNet Protocol & WHO Specifications Archive**. This document serves as the official open-access registry and cross-check inventory of all technical manuals, frame syntax, dimension definitions, and PDF specifications published by BTicino / Legrand for the OpenWebNet protocol across MyHOME systems.

Historically, these technical specifications were distributed through the *MyOpen Community* portal (`myopen-legrandgroup.com` / `myopen-bticino.it`), which is no longer active. To ensure that developers, installers, and community members have permanent access to accurate protocol documentation, we maintain this centralized registry.

## 📚 Master WHO Family Inventory

The table below catalogs every known OpenWebNet function family (`WHO`), its official Legrand document title, current known version, archive status, and Home Assistant platform mapping.

### Status Legend
- 🟢 **Archived & Verified**: Official PDF is preserved in our archive with full syntax verified.
- 🟡 **Legacy Copy Available / Cross-Check Needed**: Legacy documentation or reverse-engineered definitions exist; seeking confirmation of the latest official version.
- 🔴 **Needed / Missing**: Seeking the official Legrand/BTicino PDF specification.

| WHO | Subsystem / Function | Official Document Title / Filename | Known Version & Date | Status | Home Assistant Entity / Platform | Notes & Supported Hardware |
|:---:|:---|:---|:---:|:---:|:---|:---|
| **0** | **Scenarios (Basic)** | `Open Web Net Language (Scenarios)` / `WHO_0.pdf` | **v2.0.0 (2010-10-01)** | 🟢 | `event`, automations | 32 standard scenarios. Legrand 03551, 88301; BTicino F420, IR interface 3456. Contributed by GianlucaCh. |
| **1** | **Lighting (Illuminazione)** | `Who = 1 LIGHTING` / `WHO_1.pdf` | **v1.1.0 (2014-11-17)** | 🟢 | `light` | ON, OFF, Dimming (1-100%, 10 levels, steps), Blink, Timer, Speed of transition. Extended lighting & DALI dimensions (tunable white / RGBW via F429/F429G). Contributed by GianlucaCh. |
| **2** | **Automation (Automazione)** | `Messages - Automation` / `WHO_2.pdf` | **v1.0.0 (2015-11-12)** | 🟢 | `cover` | Roller shutters, venetian blinds, motorized curtains, gates. Standard UP/DOWN/STOP and advanced absolute positioning percentage (0-100%, Legrand 67557). Contributed by GianlucaCh. |
| **3** | **Load Control (Legacy)** | `OpenWebNet_Community_3_LoadControl` / `WHO_3.pdf` | v1.0.0 (2006) | 🟡 | `switch`, `sensor` | Priority-based load disconnection central unit (F421). Inhibit/force actuators. |
| **4** | **Thermoregulation (Termoregolazione)** | `Open Web Net Language - Heating adjustment` / `WHO_4 2.pdf` | **v2.0.0 (2013-11-27)** | 🟢 | `climate`, `sensor` | 4-zone / 99-zone central units (3550), standalone thermostats (L/N/NT4691), external probe sensors (3475). Added dimension 22 (offset) and dimension 11 (fancoil 3-speed). Contributed by GianlucaCh. |
| **5** | **Burglar Alarm (Antifurto)** | `MyHome Burglar Alarm` / `WHO_5.pdf` | **(2008-02-13)** | 🟢 | `alarm_control_panel` | Central units (3485, 3486), partition arming/disarming, panic alarms, gas/water technical alarms, sensor zone status. Authored by Lorenzo Pini. Contributed by GianlucaCh. |
| **6** | **Door Entry Call & Lock** | `OpenWebNet_Community_DoorEntry` / `WHO_6.pdf` | v1.0.0 (2006) | 🟡 | `lock`, `switch`, `event` | Audio door entry calls, door lock release (`*6*10*<WHERE>##`), staircase light, camera switching, incoming call chimes. |
| **7** | **Video Door Entry / Multimedia** | `Open Web Net WHO=7` / `WHO_7.pdf` | **v1.0.1 (2011-12-01)** | 🟢 | `camera` | Video session establishment, camera selection, video stream routing over IP for Video Server F453AV. Contributed by GianlucaCh. |
| **9** | **Auxiliary (Comandi Ausiliari)** | `OpenWebNet_Community_Auxiliary` / `WHO_9.pdf` | v1.0.0 (2006) | 🟡 | `switch` | Auxiliary channels (AUX 1 to AUX 9) for triggering remote relays, annunciators, or inter-system signals without occupying lighting addresses. |
| **13** | **Gateway Management** | `OpenWebNet_Community_2_device_v1_0_0_EN` / `WHO_13.pdf` | **v1.0.0 (2006-06-13)** | 🟢 | Core diagnostics | Date/time synchronization (`*#13**0*...`), firmware version query, IP configuration, MAC address, uptime, reboot command. Contributed by GianlucaCh. |
| **14** | **Actuators Lock (Light & Shutters)** | `Light & Shutter Actuators Lock` *(No Public PDF)* | v1.0.0 (2008) | 🟢 | Core diagnostics, `lock`, `switch` | Physical endpoint lock/unlock. Lock (`*14*0*<WHERE>##`), Unlock (`*14*1*<WHERE>##`), Status query (`*#14*<WHERE>##`). Inverts/locks physical button input. Legrand never published a public PDF for this internal diagnostic function. |
| **15** | **CEN (Scenario Pushbuttons)** | `OpenWebNet CEN Scenario Controls` / `WHO_15.pdf` | v1.0.0 (2008) | 🟢 | `event`, automations | Physical pushbuttons with short press, start pressure, release, and hold heartbeats. Buttons 1 to 32. |
| **16** | **Sound System / Audio** | `OpenWebNet_Community_4_soundsystem_v1_0_1_EN.doc` / `WHO_16.pdf` | **v1.0.1 (2011-11-24)** | 🟢 | `media_player` | Multi-room audio matrix (F441), sources 1-4, amplifiers, volume steps 0-30, follow-me. |
| **17** | **Scene Management (MH200N)** | `MH200/MH200N Scenario Language` / `WHO_17.pdf` | v1.0.0 (2009) | 🟢 | `event`, automations | Advanced conditional scenarios on MH200/MH200N controllers. Scenarios 1 to 300. |
| **18** | **Energy Management** | `OpenWebNet Energy Management` / `WHO_18.pdf` | v1.0.0 (2010) | 🟢 | `sensor` | Power meters (F520), instantaneous active power (W), totalizer pulses, daily/monthly consumption. |
| **22** | **Sound Diffusion (Extended)** | `Sound Diffusion Extended` / `WHO_22.pdf` | v1.0.0 (2012) | 🟢 | `media_player` | Advanced multi-room spatial audio matrix routing, equalizer presets, and group zone control. |
| **24** | **Lighting Management / DALI** | `Who = 24 LIGHTING MANAGEMENT` / `WHO_24.pdf` | v1.0.0 (2015) | 🟢 | `light` | DALI ballast addressing, emergency lighting status, DALI groups via F429/F429G interfaces. |
| **25** | **CEN+ / Dry Contacts** | `OpenWebNet CEN+ Specification` / `WHO_25.pdf` | v1.0.0 (2011) | 🟢 | `event`, `binary_sensor` | Extended scenario pushbuttons (up to 255 buttons) and dry contact interfaces (3477, F428). |
| **1001** | **Diagnostic (Lighting / Bus)** | `WHO 1001 Diagnostic Specification` / `WHO_1001.pdf` | v1.0.0 (2008) | 🟢 | Core diagnostics | Bus physical health, line voltage drops, short circuit detection. |
| **1004** | **Heating Diagnostic** | `WHO 1004 Diagnostic Heating` / `WHO_1004.pdf` | v1.0.0 (2008) | 🟢 | Core diagnostics | HVAC probe faults, probe disconnected alarms, temperature sensor calibration status. |
| **1013** | **Gateway Diagnostic** | `WHO 1013 Gateway Diagnostics` / `WHO_1013.pdf` | v1.0.0 (2008) | 🟢 | Core diagnostics | Gateway TCP socket queue length, frame buffer overrun monitoring, packet drop counters. |
