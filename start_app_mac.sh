#!/usr/bin/env bash
# Lance ProtoLab sur Mac et ouvre le navigateur sur http://127.0.0.1:8030.
# Options : --port N, --no-browser, --version (contrat du portail).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "L'environnement Python est absent : lancez d'abord ./install_mac.sh"
    exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
    echo "L'interface n'est pas compilée : relancez ./install_mac.sh"
    exit 1
fi

exec .venv/bin/python backend/launcher.py "$@"
