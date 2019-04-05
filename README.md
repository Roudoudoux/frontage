# Arbalet Frontage backend

This is the backend of Arbalet Frontage, the [pixelated building facade of Bordeaux University](https://vimeo.com/arbalet/frontage). It drives 4 rows x 19 columns of RGB Art-Net/DMX fixtures. See [Network schematics](frontage.svg).



## Mesh  specifications

### Prerequise
- [esp-idf](https://github.com/espressif/esp-idf) : framework used for programming esp32
- AP dedicated to the communication between the mesh network and the backend service. It can either be your **network manager device** or a **router**.

### ESP-IDF
The framework needs to be installed from the espressif website. Several steps are required and each one of them is needed.

To generate the **esp-idf** documentation, the doxyfile has to be slightly modified.

### Quick Starter for ESP
- Connect an esp32 with a serial USB cable allowing data transfert.
- Generate a `sdkconfig` file with `make menuconfig`
- Enter in `example configuration` and set the right configuration for your access point.
- Compile and flash your esp32 with `make flash`
- Unplug the esp32.

**Tips :**
- Monitoring can be done by `make monitor` or `make simple_monitor`. The latter is to be used in case of no code compilation.
- If there is a need to monitor several esp32 at once with one computer, copy/paste the esp directory and modify the line `CONFIG_ESPTOOLPY_PORT="/dev/ttyUSB0"` in `sdkconfig` by incrementing the `ttyUSB` in the copied directory. You can also use `make menuconfig` in serial flasher config menu.
- Whenever you want to build your code, use `make -j4 build`, it will be much more faster than `make build`

### Configuring AP

The default configuration is :
- **ssid :**  `ArbaMesh`
- **security :** `WPA/WPA2`
- **password :** `arbampass`
- **IPv4 :** `10.42.0.1`
- **Port :** `9988`

**Note :** All the default parameters are fixed as ESP32 embarked programing requires constant values. If a change is required due to devices, make sure to change the esp32 code in `mesh_main.c` along with `docker-compose.yml` for Ipv4 address and port. If the change is about **ssid**, **password** or **security** the changes only apply in the `sdkconfig` file (esp directory). This can be done with `make menuconfig`.

## Development
### First startup
Default keys and passwords are fine for a dev environment.
Make sure [docker-compose](https://docs.docker.com/compose/) is installed on your workstation and then build and run with docker:
```
git clone https://github.com/arbalet-project/frontage.git
cd frontage
docker-compose run --rm app init # Prompt will ask you to create your admin password
```
Now you have to set up your access point as explained in the ACCESS POINT section, and edit your `docker-compose.yml` file to change the specified IP address of the mesh component to the IP address of your server. Once it's done, you can start the project
```
docker-compose up
```
If everything goes well, your terminal shows the Arbalet Frontage scheduler state on stdout:
```
scheduler_1  |  ========== Scheduling ==========
scheduler_1  | -------- Enable State
scheduler_1  | scheduled
scheduler_1  | -------- Is Frontage Up?
scheduler_1  | False
scheduler_1  | -------- Usable?
scheduler_1  | False
scheduler_1  | -------- Current App
scheduler_1  | {}
scheduler_1  | ---------- Forced App ?
scheduler_1  | False
scheduler_1  | ---------- Waiting Queue
scheduler_1  | []
frontage_mesh_1 | Socket opened, waiting for connection...
```
Once the pixels have been addressed, you should see a prompt like that :
```
frontage_mesh_1 |  ========== Mesh ==========
frontage_mesh_1 | -------- Is mesh initialized :
frontage_mesh_1 | True
frontage_mesh_1 | -------- Color frame sent :
frontage_mesh_1 | 2500
frontage_mesh_1 | -------- Pixels amount declared ?
frontage_mesh_1 | 3
frontage_mesh_1 | -------- Pixels amount required ?
frontage_mesh_1 | 3
frontage_mesh_1 | -------- Pixels?
frontage_mesh_1 | {'48:174:164:24:27:184': ((0, 2), 0), '48:174:164:24:26:72': ((0, 0), 1), '48:174:164:24:59:96': ((0, 1), 2)}
frontage_mesh_1 | -------- Pixels deconnected?
frontage_mesh_1 | {}
frontage_mesh_1 | -------- Pixels unknown?
frontage_mesh_1 | {}
```
* Enable state can be `on` (forced on), `scheduled` (according to the daily planning based on sunset time) or `off` (forced off)
* Frontage is up in forced on or when the server's local time is within the range of the daily planning, or when in forced on mode
* Frontage is usable when a regular user is allowed to connect and take control (i.e. when frontage is up and no application is being forced)
* Current app shows the current running f-app (frontage application)
* Forced app is true is the current running f-app is being forced by and admin (will stop only when unforced)
* Waiting queue shows the list of users waiting for controlling the frontage

If you're meeting authorizations issues on Linux, make sure your username is in the docker group: `sudo usermod -aG docker $USER` Log out and log back in so that your group membership is re-evaluated.

If the mesh component has trouble starting up, please make sure that you're connected to your access point, that its specified IP address is valid, and that the port is available.

Then compile, deploy and open [the frontend app](https://github.com/arbalet-project/frontage-frontend) and edit its environment so that it calls the IP of your dev workstation (usually `127.0.0.1` in `environment.ts`)

If you want to stop the backend, just press Ctl+C once, it will nicely closes all processes.

## Production
Refer to the [install](install) procedure to deploy the app on a production server.

## How to...?
### Reset database and settings
`docker-compose down -v` will get rid of the database, you will then need to initialize a new one with `docker-compose run --rm app init`. If this is intended to be executed on the production server, add `-f docker-compose.prod.yml` to the `docker-compose commands`.
