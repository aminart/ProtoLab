"""Entry point of ProtoLab.exe: starts the local server and opens the browser.

Portal contract (same options in every app of the suite):
    ProtoLab.exe [--port 8030] [--no-browser] [--version]
    GET /health -> {"status": "ok", "app": "protolab", "name": "ProtoLab", "version": "..."}
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app_info import APP_ID, APP_NAME, DEFAULT_PORT, VERSION

HOST = "127.0.0.1"


def _is_app_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=1) as response:
            return response.status == 200 and json.loads(response.read()).get("app") == APP_ID
    except (OSError, ValueError):
        return False


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, port)) != 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def _open_when_ready(url: str, port: int) -> None:
    for _ in range(60):
        if _is_app_running(port):
            webbrowser.open(url)
            return
        time.sleep(0.5)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ProtoLab", description=f"{APP_NAME} : serveur local")
    parser.add_argument("--port", type=int, default=None,
                        help=f"port d'écoute (défaut {DEFAULT_PORT}) ; s'il est pris par une autre application, le lancement échoue")
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur (lancement par le portail)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    port = args.port or DEFAULT_PORT
    url = f"http://{HOST}:{port}"

    if _is_app_running(port):
        # Already running (e.g. double-clicked twice): just show it.
        print(f"{APP_NAME} est déjà lancé sur {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return

    if not _port_is_free(port):
        if args.port is not None:
            # Port imposed (by the portal): never move silently, the caller would look in the wrong place.
            print(f"Le port {port} est déjà utilisé par une autre application : {APP_NAME} ne peut pas démarrer.",
                  file=sys.stderr)
            sys.exit(2)
        port = _free_port()
        url = f"http://{HOST}:{port}"

    print(f"{APP_NAME} {VERSION}")
    print(f"L'application est disponible sur {url}")
    print("Gardez cette fenêtre ouverte pendant l'utilisation ; fermez-la pour arrêter l'application.")
    sys.stdout.flush()

    # Imported here so the window shows the message above while the app loads.
    from main import app

    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
