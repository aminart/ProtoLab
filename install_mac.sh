#!/usr/bin/env bash
# Installation de ProtoLab sur Mac : environnement Python, dépendances, interface compilée.
# À relancer après chaque mise à jour du code (git pull).
set -euo pipefail
cd "$(dirname "$0")"

echo "====================================="
echo "Installation de ProtoLab (Mac)"
echo "====================================="

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python est introuvable : installez Python 3.11 ou plus récent depuis https://www.python.org/downloads/macos/"
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "Python 3.11 ou plus récent est nécessaire (version trouvée : $(python3 --version))."
    echo "Installez-le depuis https://www.python.org/downloads/macos/ puis relancez ce script."
    exit 1
fi
if ! command -v npm >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)'; then
    echo "Node.js 20 ou plus récent est nécessaire : installez la version LTS depuis https://nodejs.org"
    exit 1
fi
if ! git --version >/dev/null 2>&1; then
    echo "git est nécessaire (il télécharge le design system Night Navy)."
    echo "Lancez : xcode-select --install   puis relancez ce script."
    exit 1
fi

echo
echo "[1/3] Environnement Python..."
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

echo
echo "[2/3] Dépendances de l'interface..."
(cd frontend && npm ci)

echo
echo "[3/3] Compilation de l'interface et du lecteur de prototype..."
(cd frontend && npm run build)

chmod +x start_app_mac.sh "Lancer ProtoLab.command" 2>/dev/null || true
echo
echo "Installation terminée."
echo "Lancez ProtoLab avec : ./start_app_mac.sh   (ou double-clic sur « Lancer ProtoLab.command »)"
