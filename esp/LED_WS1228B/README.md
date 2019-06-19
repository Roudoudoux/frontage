# Code for the ESP Cards

The ESP cards are state machines, that will receive and send different kinds of frames depending on their state.

[TODO : describe quickly the state machine]

## How to use

- First, enter your Access Point configuration, using the 'make menuconfig' command, and editing the 'Exemple configuration > Router SSID and Router Password' menu

- Make sure that the port in 'Serial Flasher Config' is the one your esp is connected to.

- to flash on the card, use 'make flash'.You can see the logs using the 'make monitor' command, as long as the card is connected to the same port.
