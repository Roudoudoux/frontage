# Assisted Manual Addressing

This exemple show how the Assisted Manual Addressing works. There is no checking on errors occuring within the system.

## How to use :

- Configure the AP and its password using 'make menuconfig', and editing the 'exemple configuration > Router SSID and Router PASSWORD' menu. Make sure that 'Serial Flasher Config > serial port' corresponds to the port the ESP is connected to.

- To flash it on the card, use 'make flash'. You can check the logs using 'make monitor' as long as the card is connected to the proper port.

- Make sure that port 8080 is open and free, or change it in the server file and the 'main/mesh_main.c' file.

- execute the server using a python executor, and run the cards.
