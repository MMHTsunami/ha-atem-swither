# Blackmagic ATEM Switcher for Home Assistant

An early-stage Home Assistant custom integration for Blackmagic Design ATEM
switchers.

## Installation

Copy `custom_components/atem_switcher` into the Home Assistant
`custom_components` directory, restart Home Assistant, then add **Blackmagic
ATEM Switcher** from **Settings → Devices & services**.

Enter the switcher's IP address. Setup checks the ATEM UDP handshake on port
9910 before creating the integration.

## Current status

The initial foundation includes asynchronous UDP handshake handling, packet and
field decoding, connection status, and a diagnostic sensor counting distinct
field types received.
Program/preview/Aux controls, switcher model discovery, and the remaining state
entities are not implemented yet.
