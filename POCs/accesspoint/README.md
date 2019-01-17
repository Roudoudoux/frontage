# Access Point

Le serveur communique avec les ESP32 par un réseau WiFi. Pour ce faire le PC doit émettre un réseau WiFi sur lequel la carte root des ESP32 vient se connecter.


## Create_ap

_Create_ap_ est utilisée pour créer un accesspoint et est disponible sur le dépôt git suivant [](https://github.com/oblique/create_ap)[^1].

Pour que _create_ap_ fonctionne, il faut que la carte réseau <ifname> ne soit pas gérée par networkmanager. Pour ce faire, il on peut modifier le fichier _/etc/NetworkManager/NetworkManager.conf_ en ajoutant :
~~~~~~
[keyfile]
unmanaged-devices=interface-name:<ifname>
~~~~~~
Il faut redémarer le service NetworkManager pour que le changement soit effectif.

## Configuration de l'accesspoint

L'accesspoint doit :
- avoir l'adresse IP statique 10.0.0.1
- être proteger par WPA2
- avoir pour SSID "arbaletMesh"

Dans le fichier _backend/accesspoint/accesspoint.conf_ modifier les valeurs de :

- WIFI_IFACE par le nom de votre carte réseau (utilisée comme access point)
- INTERNET_IFACE par le nom de l'interface réseau connectée à internet
- PASSPHRASE par votre mot de passe

Entrer la commande _create_ap --config ~/backend/accesspoint/accesspoint.conf_ en mode super-utilisateur pour lancer le partage de connexion.

[^1]: consultée pour la dernière fois le 16 Janvier 2019
