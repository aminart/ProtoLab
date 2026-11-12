# Lancer ProtoLab sur Mac

ProtoLab tourne sur Mac depuis le code source : pas d’application à télécharger. Une installation au départ (une dizaine de minutes), puis une commande ou un double-clic pour lancer l’app.

Fonctionne sur macOS 12 (Monterey) et plus récent, processeur Intel ou Apple.

## 1. Installer les outils (une seule fois)

Ouvrir le **Terminal** (Applications › Utilitaires › Terminal).

1. **Outils de développement Apple** (ils apportent `git`) :
   ```bash
   xcode-select --install
   ```
   Une fenêtre s’ouvre : cliquer sur « Installer ». Si le Terminal répond que les outils sont déjà installés, passer à la suite.

2. **Python 3.12** : sur https://www.python.org/downloads/macos/, télécharger le « macOS 64-bit universal2 installer » de la dernière version 3.12 et l’installer.
   Puis, dans le Finder, ouvrir **Applications › Python 3.12** et double-cliquer sur **Install Certificates.command**.

3. **Node.js** : sur https://nodejs.org, télécharger la version **LTS** (fichier `.pkg`) et l’installer.

4. **Fermer le Terminal et en ouvrir un nouveau**, puis vérifier :
   ```bash
   python3 --version   # Python 3.11 ou plus récent
   node --version      # v20 ou plus récent
   git --version
   ```
   Si `python3 --version` affiche encore 3.9, c’est le Python d’Apple : le nouveau Terminal n’a pas été ouvert après l’installation de Python 3.12.

## 2. Récupérer le code

```bash
cd ~/Documents
git clone https://github.com/aminart/ProtoLab.git
cd ProtoLab
```

Passer par `git clone` plutôt que par le bouton « Download ZIP » de GitHub : un zip téléchargé par le navigateur est marqué « venant d’Internet », et macOS bloque alors le double-clic sur les scripts.

Tant que la première version n’est pas fusionnée dans `main`, se placer sur sa branche :

```bash
git checkout claude/protolab-v1
```

## 3. Installer ProtoLab

Dans le dossier `ProtoLab` :

```bash
./install_mac.sh
```

Le script vérifie les outils, crée l’environnement Python (`.venv`), installe les dépendances et compile l’interface. Compter quelques minutes la première fois.

## 4. Lancer ProtoLab

Au choix :

- dans le Terminal, depuis le dossier `ProtoLab` :
  ```bash
  ./start_app_mac.sh
  ```
- ou, dans le Finder, double-clic sur **Lancer ProtoLab.command**. La première fois, si macOS refuse de l’ouvrir : clic droit › Ouvrir › Ouvrir.

Le navigateur s’ouvre sur http://127.0.0.1:8030. **Garder la fenêtre du Terminal ouverte** pendant l’utilisation : la fermer (ou taper Ctrl + C) arrête ProtoLab.

Options utiles :

```bash
./start_app_mac.sh --port 8031      # si le port 8030 est déjà pris
./start_app_mac.sh --no-browser     # sans ouvrir le navigateur
./start_app_mac.sh --version
```

## 5. Connecter le modèle IA

Dans ProtoLab, roue crantée › Paramètres : URL du service, clé API, certificat de l’entreprise, modèle — comme dans SpecGen.

Sur Mac, la clé API est rangée dans le **trousseau** de session (application Trousseau d’accès, élément « ProtoLab ») ; elle n’est jamais écrite en clair sur le disque.

Sans connexion au modèle, ProtoLab fonctionne quand même : import des sources, structure, navigation du prototype, versions figées et export HTML.

## Mettre à jour

```bash
cd ~/Documents/ProtoLab
git pull
./install_mac.sh
```

## Où sont mes données ?

Dans `~/.config/protolab` : les projets (sources, réglages, versions figées), le design system global et les paramètres de connexion. Supprimer ce dossier remet ProtoLab à zéro (la clé reste dans le trousseau jusqu’à « Effacer les paramètres »).

## En cas de problème

| Message | Solution |
|---|---|
| `Python 3.11 ou plus récent est nécessaire` | Installer Python 3.12 (étape 1.2), puis ouvrir un nouveau Terminal. |
| `git est nécessaire` | `xcode-select --install`, puis relancer `./install_mac.sh`. |
| `CERTIFICATE_VERIFY_FAILED` pendant l’installation | Double-cliquer sur **Install Certificates.command** (Applications › Python 3.12). Sur un réseau d’entreprise, se connecter hors VPN pour l’installation. |
| `permission denied: ./install_mac.sh` | `chmod +x install_mac.sh start_app_mac.sh "Lancer ProtoLab.command"` |
| `Le port 8030 est déjà utilisé` | ProtoLab est peut-être déjà ouvert dans un autre Terminal ; sinon `./start_app_mac.sh --port 8031`. |
| Page blanche ou ancienne interface | Relancer `./install_mac.sh` (il recompile l’interface). |
