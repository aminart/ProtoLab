"""Builds the Figma fixtures (REST API format) used by the tests:

    python tests/make_fixtures.py

A small "Portail des demandes": a Prototype page with 4 frames (Connexion, Liste des demandes,
Nouvelle demande, Frame orpheline) in auto-layout, built from library instances (Input, Button,
Carte demande), plus a Brouillons page. And the library file of the project.
"""
from __future__ import annotations

import json
from itertools import count
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_ids = count(10)

INK = {"r": 0.11, "g": 0.12, "b": 0.16, "a": 1}
WHITE = {"r": 1, "g": 1, "b": 1, "a": 1}
PRIMARY = {"r": 0.05, "g": 0.37, "b": 0.32, "a": 1}
LINE = {"r": 0.8, "g": 0.82, "b": 0.85, "a": 1}


def nid() -> str:
    return f"1:{next(_ids)}"


def box(x: float, y: float, w: float, h: float) -> dict:
    return {"x": x, "y": y, "width": w, "height": h}


def text(name: str, characters: str, x: float, y: float, w: float, h: float, size: int = 15, weight: int = 400, color=INK, **extra) -> dict:
    return {
        "id": nid(), "name": name, "type": "TEXT", "characters": characters,
        "absoluteBoundingBox": box(x, y, w, h), "fills": [{"type": "SOLID", "color": color}],
        "style": {"fontFamily": "Roboto", "fontWeight": weight, "fontSize": size, "lineHeightPx": size * 1.4, "lineHeightUnit": "PIXELS", "textAlignHorizontal": "LEFT"},
        "textAutoResize": extra.pop("resize", "HEIGHT"), "layoutAlign": "STRETCH", **extra,
    }


def frame(name: str, x: float, y: float, w: float, h: float, children: list, mode: str | None = "VERTICAL", **extra) -> dict:
    node = {"id": extra.pop("id", None) or nid(), "name": name, "type": extra.pop("type", "FRAME"), "absoluteBoundingBox": box(x, y, w, h),
            "fills": extra.pop("fills", []), "children": children, **extra}
    if mode:
        node.update({"layoutMode": mode, "itemSpacing": node.get("itemSpacing", 8), "primaryAxisSizingMode": node.get("primaryAxisSizingMode", "AUTO"),
                     "counterAxisSizingMode": node.get("counterAxisSizingMode", "FIXED")})
    return node


def input_field(label: str, placeholder: str, x: float, y: float, w: float = 342) -> dict:
    return frame(
        "Input", x, y, w, 72,
        [
            text("Label", label, x, y, w, 20, size=14, weight=500),
            frame("Field", x, y + 24, w, 44, [text("Placeholder", placeholder, x + 12, y + 36, w - 24, 20, color={"r": 0.4, "g": 0.42, "b": 0.47, "a": 1})],
                  mode="HORIZONTAL", paddingLeft=12, paddingRight=12, paddingTop=12, paddingBottom=12, cornerRadius=6,
                  fills=[{"type": "SOLID", "color": WHITE}], strokes=[{"type": "SOLID", "color": LINE}], strokeWeight=1, strokeAlign="INSIDE",
                  layoutAlign="STRETCH", primaryAxisSizingMode="FIXED", counterAxisSizingMode="AUTO"),
        ],
        type="INSTANCE", componentId="c:input", layoutAlign="STRETCH", itemSpacing=4,
    )


def button(label: str, x: float, y: float, w: float, interactions: list | None = None) -> dict:
    node = frame(
        "Button", x, y, w, 44, [text("Label", label, x + 16, y + 12, w - 32, 20, size=15, weight=600, color=WHITE, resize="WIDTH_AND_HEIGHT")],
        mode="HORIZONTAL", type="INSTANCE", componentId="c:button-primary", paddingLeft=16, paddingRight=16, paddingTop=12, paddingBottom=12,
        primaryAxisAlignItems="CENTER", counterAxisAlignItems="CENTER", cornerRadius=6, fills=[{"type": "SOLID", "color": PRIMARY}],
        primaryAxisSizingMode="AUTO", counterAxisSizingMode="AUTO",
    )
    if interactions:
        node["interactions"] = interactions
    return node


def card(title: str, amount: str, x: float, y: float) -> dict:
    return frame(
        "Carte demande", x, y, 342, 64,
        [text("Objet", title, x + 12, y + 10, 318, 22, weight=600), text("Montant", amount, x + 12, y + 34, 318, 20, size=14)],
        type="INSTANCE", componentId="c:card", paddingLeft=12, paddingTop=10, paddingRight=12, paddingBottom=10, itemSpacing=2,
        fills=[{"type": "SOLID", "color": WHITE}], strokes=[{"type": "SOLID", "color": LINE}], strokeWeight=1, cornerRadius=8,
        effects=[{"type": "DROP_SHADOW", "visible": True, "color": {"r": 0, "g": 0, "b": 0, "a": 0.08}, "offset": {"x": 0, "y": 1}, "radius": 3, "spread": 0}],
        layoutAlign="STRETCH",
        interactions=[{"trigger": {"type": "ON_CLICK"}, "actions": [{"type": "NODE", "destinationId": "1:3", "navigation": "NAVIGATE"}]}],
    )


def screen(frame_id: str, name: str, x: float, children: list) -> dict:
    return frame(name, x, 0, 390, 844, children, id=frame_id, paddingLeft=24, paddingRight=24, paddingTop=32, paddingBottom=32, itemSpacing=16,
                 fills=[{"type": "SOLID", "color": {"r": 0.97, "g": 0.97, "b": 0.98, "a": 1}}], primaryAxisSizingMode="FIXED", clipsContent=True)


def mockup() -> dict:
    connexion = screen("1:1", "01 - Connexion", 0, [
        text("Titre", "Portail des demandes", 24, 32, 342, 34, size=24, weight=700),
        input_field("E-mail", "prenom.nom@entreprise.fr", 24, 82),
        input_field("Mot de passe", "••••••••", 24, 170),
        button("Se connecter", 24, 258, 140, [{"trigger": {"type": "ON_CLICK"}, "actions": [{"type": "NODE", "destinationId": "1:2", "navigation": "NAVIGATE"}]}]),
    ])
    liste = screen("1:2", "Liste des demandes", 500, [
        text("Titre", "Mes demandes", 524, 32, 342, 34, size=24, weight=700),
        frame("Liste", 524, 82, 342, 216, [card("Achat de licences", "320 €", 524, 82), card("Formation Figma", "450 €", 524, 156), card("Écran 27 pouces", "280 €", 524, 230)],
              itemSpacing=10, layoutAlign="STRETCH"),
        button("Nouvelle demande", 524, 320, 180),
    ])
    nouvelle = screen("1:3", "Nouvelle demande v2", 1000, [
        text("Titre", "Nouvelle demande", 1024, 32, 342, 34, size=24, weight=700),
        input_field("Objet", "Ex. : achat de matériel", 1024, 82),
        input_field("Montant (€)", "0", 1024, 170),
        frame("Actions", 1024, 258, 342, 44, [
            button("Envoyer", 1024, 258, 120),
            {"id": nid(), "name": "Retour", "type": "TEXT", "characters": "Annuler", "absoluteBoundingBox": box(1160, 270, 60, 20),
             "fills": [{"type": "SOLID", "color": PRIMARY}], "style": {"fontFamily": "Roboto", "fontSize": 15, "fontWeight": 500},
             "textAutoResize": "WIDTH_AND_HEIGHT",
             "interactions": [{"trigger": {"type": "ON_CLICK"}, "actions": [{"type": "BACK"}]}]},
        ], mode="HORIZONTAL", itemSpacing=16, counterAxisAlignItems="CENTER", layoutAlign="STRETCH"),
        {"id": nid(), "name": "Icône", "type": "VECTOR", "absoluteBoundingBox": box(1024, 320, 24, 24), "size": {"x": 24, "y": 24},
         "fills": [{"type": "SOLID", "color": PRIMARY}], "fillGeometry": [{"path": "M2 2L22 2L22 22L2 22Z", "windingRule": "NONZERO"}]},
    ])
    orpheline = frame("Bandeau d'aide", 1500, 0, 390, 300, [
        text("Aide", "Besoin d'aide ?", 1524, 40, 200, 24, size=18, weight=700, resize="WIDTH_AND_HEIGHT"),
        {"id": nid(), "name": "Illustration", "type": "RECTANGLE", "absoluteBoundingBox": box(1524, 80, 200, 120), "fills": [{"type": "IMAGE", "imageRef": "abc"}]},
    ], mode=None, id="1:4")
    return {
        "name": "Portail des demandes – maquette",
        "document": {"id": "0:0", "type": "DOCUMENT", "children": [
            {"id": "0:1", "name": "Brouillons", "type": "CANVAS", "children": [screen("9:1", "Vieille idée", 0, [])]},
            {"id": "0:2", "name": "🟢 Prototype", "type": "CANVAS", "children": [connexion, liste, nouvelle, orpheline]},
        ]},
        "components": {
            "c:input": {"key": "key-input", "name": "State=Default", "componentSetId": "cs:input", "remote": True},
            "c:button-primary": {"key": "key-button", "name": "Type=Primary", "componentSetId": "cs:button", "remote": True},
            "c:card": {"key": "key-card", "name": "Carte demande", "remote": True},
        },
        "componentSets": {
            "cs:input": {"key": "set-input", "name": "Input", "remote": True},
            "cs:button": {"key": "set-button", "name": "Button", "remote": True},
        },
    }


def project_library() -> dict:
    return {
        "name": "Portail – bibliothèque projet",
        "document": {"id": "0:0", "type": "DOCUMENT", "children": [{"id": "0:1", "name": "Composants", "type": "CANVAS", "children": [
            {"id": "5:1", "name": "Carte demande", "type": "COMPONENT", "absoluteBoundingBox": box(0, 0, 342, 64), "children": [],
             "fills": [{"type": "SOLID", "color": WHITE}], "styles": {"fill": "S:1"}},
        ]}]},
        "components": {"5:1": {"key": "key-card", "name": "Carte demande"}},
        "styles": {"S:1": {"key": "s1", "name": "Surface/Default", "styleType": "FILL"}},
    }


def global_variables() -> dict:
    return {"status": 200, "error": False, "meta": {
        "variableCollections": {"VC:1": {"id": "VC:1", "name": "Couleurs", "defaultModeId": "m1", "modes": [{"modeId": "m1", "name": "Clair"}]}},
        "variables": {
            "V:1": {"id": "V:1", "name": "color/primary", "resolvedType": "COLOR", "variableCollectionId": "VC:1", "valuesByMode": {"m1": {"r": 0.05, "g": 0.37, "b": 0.32, "a": 1}}},
            "V:2": {"id": "V:2", "name": "color/error", "resolvedType": "COLOR", "variableCollectionId": "VC:1", "valuesByMode": {"m1": {"type": "VARIABLE_ALIAS", "id": "V:3"}}},
            "V:3": {"id": "V:3", "name": "red/600", "resolvedType": "COLOR", "variableCollectionId": "VC:1", "valuesByMode": {"m1": {"r": 0.85, "g": 0.18, "b": 0.13, "a": 1}}},
            "V:4": {"id": "V:4", "name": "spacing/md", "resolvedType": "FLOAT", "variableCollectionId": "VC:1", "valuesByMode": {"m1": 16}},
        },
    }}


def global_components() -> dict:
    return {
        "name": "Design system",
        "document": {"id": "0:0", "type": "DOCUMENT", "children": [{"id": "0:1", "name": "Composants", "type": "CANVAS", "children": [
            {"id": "7:1", "name": "Input", "type": "COMPONENT_SET", "absoluteBoundingBox": box(0, 0, 342, 72), "children": [
                {"id": "7:2", "name": "State=Default", "type": "COMPONENT", "absoluteBoundingBox": box(0, 0, 342, 72), "children": []},
                {"id": "7:3", "name": "State=Error", "type": "COMPONENT", "absoluteBoundingBox": box(0, 80, 342, 72), "children": []},
            ]},
        ]}]},
        "components": {"7:2": {"key": "key-input", "name": "State=Default", "componentSetId": "7:1"}, "7:3": {"key": "key-input-error", "name": "State=Error", "componentSetId": "7:1"}},
        "componentSets": {"7:1": {"key": "set-input", "name": "Input"}},
    }


if __name__ == "__main__":
    FIXTURES.mkdir(exist_ok=True)
    for name, data in (("figma_mockup.json", mockup()), ("project_library.json", project_library()),
                       ("global_variables.json", global_variables()), ("global_components.json", global_components())):
        (FIXTURES / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("écrit", name)
