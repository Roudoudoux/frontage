## Objectif

Les ESP32 communiquent entre elles via le réseau mesh et transmettent leur adresse mac à l'ESP32 **root**.
L'ESP32 **root** transmet les adresses mac de toutes les cartes ESP32 (elle incluse) au serveur.

L'ESP32 **root** et le PC hébergeant le serveur sont connecté en mode **ad-hoc**.

## Code des ESP32

Le dossier **esp_code** contient l'ensemble des fichiers nécessaire à la compilation et au téléversement sur une carte ESP32. Toutes les ESP32 présentent sur le réseau mesh ont le même code à leur bord (l'élection de l'ESP32 **root** s'effectue automatiquement).

Pour téléverser le code sur une carte :
- Brancher la carte à l'aide d'un cable sérial USB.
- Se mettre dans le dossier esp_code.
- Entrer la commande : _make flash_.

## Code serveur

Le PC doit être en mode **access point** et avoir l'adresse **IP statique : 10.0.0.1**.
Le serveur se lance en entrant la commande _python server.py_.

## Notes

Pour monitorer les affichages d'une carte ESP32 branchée à un PC, entrer la commande _make monitor_ dans le dossier **esp_code**.

Si l'erreur "make: *** Aucune règle pour fabriquer la cible « /make/project.mk ». Arrêt." survient, vérifiez que les variables d'environnement **PATH**, **IDF_PATH** et **MDF_PATH** sont bien initialisées.
