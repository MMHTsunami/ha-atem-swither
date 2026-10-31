# GitHub Copilot Instructions: Home Assistant Blackmagic ATEM Integration

## Project Architecture & Tech Stack
- **Framework:** Home Assistant Core Custom Integration (`custom_components/atem_switcher`)
- **Language:** Python 3.11+ with strict type hinting (`from __future__ import annotations`).
- **Communication Protocol:** UDP (Port 9910) following the Blackmagic Design ATEM switcher protocol.
- **Async Standard:** Fully asynchronous (`asyncio`) design using non-blocking network I/O.

---

## Core Component Modules

### 1. Discovery & Config Flow (`config_flow.py`)
- **Network Discovery:** 
  - Implement UDP broadcast listening or targeted subnet scanning on port `9910` to auto-detect ATEM switchers on the local network.
  - Implement Zeroconf/mDNS discovery if advertised by the switcher model.
- **Config Flow Steps:**
  - `user`: Prompt for IP address with an option for "Auto-Discover".
  - `discovery`: Handle auto-discovered switchers, displaying the detected model name and IP address in the HA UI.
  - Validate connection by establishing a brief handshake with the switcher before saving the config entry.

### 2. Coordinator & Data Update (`coordinator.py`)
- Implement `DataUpdateCoordinator` (or a persistent persistent-connection listener) to maintain a live UDP socket connection to the ATEM switcher.
- Handle state synchronization, packet parsing (commands like `InPr` for input preview, `PrgI` for program input, `AuxS` for auxiliary outputs, and device info parsing for model identification).
- Implement robust reconnection logic with exponential backoff if network connection drops.

### 3. Device Model Auto-Detection (`const.py` / `coordinator.py`)
- Parse the initial connection/state packet header from the ATEM switcher to extract the hardware model identifier (e.g., ATEM Mini Pro, ATEM Constellation 8K, Television Studio).
- Dynamically register the device in the Home Assistant Device Registry with the correct manufacturer ("Blackmagic Design"), model name, and firmware version.

### 4. Entities & Platforms (`select.py`, `sensor.py`, `binary_sensor.py`)
- **Select Entities (`select.py`):**
  - Create individual `select` entities for **Program**, **Preview**, and each **Aux Output** (e.g., `select.atem_aux_1`).
  - Populate dropdown options dynamically based on the switcher's available video inputs (Camera 1-8, SDI, HDMI, Black, Color Bars, etc.) and custom labels retrieved from the switcher.
- **Sensors (`sensor.py`):**
  - Video mode / frame rate sensor.
  - Stream / recording status sensors (if model supports it, e.g., ATEM Mini series).
- **Binary Sensors (`binary_sensor.py`):**
  - Connection state (`Connected`/`Disconnected`).
  - Tally active states per input.

---

## Coding Standards & Best Practices

1. **Home Assistant Guidelines:**
   - Never block the event loop. Use `hass.async_add_executor_job` only for synchronous blocking legacy libraries if necessary, but prefer native `asyncio` UDP protocols (`asyncio.DatagramProtocol`).
   - Use `ConfigEntry` lifecycle methods (`async_setup_entry`, `async_unload_entry`).
   - Store runtime client/coordinators in `hass.data[DOMAIN][entry.entry_id]`.
   - Internationalization: All user-facing strings must be defined in `translations/en.json`.

2. **Error Handling & Logging:**
   - Gracefully catch `asyncio.TimeoutError`, `ConnectionRefusedError`, and malformed packet exceptions.
   - Use descriptive log prefixes: `_LOGGER.error("Failed to connect to ATEM switcher at %s: %s", host, err)`.

3. **Testing & Code Quality:**
   - Write unit tests for config flow, discovery, and packet state translation using `pytest-homeassistant-custom-component`.
   - Maintain PEP 8 compliance, clean docstrings, and strict type annotations on all public methods.