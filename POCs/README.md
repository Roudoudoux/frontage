# Proofs Of Concept

## Index

- POC1 : Connexion d'une ESP32 à un PC via un point de rendez-vous externe
- POC2 : Les ESP32 se connectent via le réseau mesh implémenté par esp-mesh. Les ESP32 non root clignotent n+1 fois (n étant fixé par l'utilisateur)

## Architecture des dossiers POC

  Un dossier POC* contient :

  - un fichier README.md;
  - un dossier **server_code** contenant les sources du serveur;
  - un dossier **esp_code** étant compatible avec le framework _esp-mesh_.

## Prérequis

- python 3.2.7
- esp-mdf
- esp-idf
