"""What the model adds to the prototype, always as small JSON objects checked against the screen.

Two kinds of requests, each short enough for a "small" model:
    - the context document → the business objects and a set of realistic starting data;
    - one screen at a time (its outline, its spec, the flow around it) → its behaviours:
      rules of the fields, effect of the buttons, lists bound to the data, texts of the detail.
The model never writes code: anything that does not match the screen (unknown layer, field,
screen) is dropped and reported.
"""
from __future__ import annotations

import re
from typing import Any

from context_reader import ContextDocument, normalize
from figma_reader import iter_nodes, outline, repeat_groups
from openai_client import complete_json

MAX_CONTEXT_CHARS = 24_000
MAX_SPEC_CHARS = 14_000
FIELD_TYPES = {"text", "long_text", "number", "date", "email", "phone", "enum", "boolean"}
FORMATS = {"text", "long_text", "number", "date", "email", "phone"}
ACTION_TYPES = {"navigate", "submit", "delete", "back", "set"}
OPERATORS = {">", ">=", "<", "<=", "==", "!=", "empty", "not_empty"}
SEED_RECORDS = 6


def slug(text: str) -> str:
    return re.sub(r"\s+", "_", normalize(str(text))).strip("_")[:40]


# --- Context → business objects and starting data -----------------------------------

CONTEXT_SYSTEM = (
    "Tu es un designer UX qui prépare un prototype de test utilisateur. Tu lis la description fonctionnelle "
    "d’une application et tu en tires les objets métier et un jeu de données fictives réalistes, en français. "
    "Tu réponds uniquement avec un objet JSON valide, sans texte autour."
)


def context_prompt(context: ContextDocument, screens: list[dict[str, Any]]) -> str:
    screen_lines = "\n".join(f"- {screen['name']}" for screen in screens) or "- (aucun écran listé)"
    return f"""Document de contexte de l’application (extrait) :
<<<
{context.text_without_diagrams(MAX_CONTEXT_CHARS)}
>>>

Écrans de l’application :
{screen_lines}

Réponds avec ce JSON :
{{
  "entities": [
    {{"name": "demande", "label": "Demande", "fields": [
      {{"name": "objet", "label": "Objet", "type": "text"}},
      {{"name": "montant", "label": "Montant (€)", "type": "number"}},
      {{"name": "statut", "label": "Statut", "type": "enum", "options": ["Brouillon", "En attente", "Validée"]}}
    ]}}
  ],
  "seed": {{"demande": [{{"id": "demande_1", "objet": "…", "montant": 120, "statut": "En attente"}}]}},
  "profiles": [{{"name": "Demandeur", "description": "…"}}]
}}

Règles :
- 1 à 6 entités : seulement les objets que les écrans affichent, créent ou modifient. Une entité « utilisateur » seulement si l’app affiche ou gère des personnes.
- "name" en snake_case sans accents ; "label" en français.
- Types de champs : text, long_text, number, date, email, phone, enum (avec "options"), boolean.
- {SEED_RECORDS} enregistrements par entité, variés et crédibles pour le métier décrit, en français. Dates au format AAAA-MM-JJ. Chaque enregistrement a un "id" unique.
- N’invente pas de fonctionnalité absente du document."""


def _coerce(value: Any, field_type: str) -> Any:
    if value is None:
        return None
    if field_type == "number":
        if isinstance(value, (int, float)):
            return value
        try:
            number = float(str(value).replace(",", ".").replace(" ", "").replace(" ", ""))
            return int(number) if number.is_integer() else number
        except ValueError:
            return None
    if field_type == "boolean":
        return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "oui", "yes", "1", "vrai")
    return value if isinstance(value, str) else str(value)


def clean_analysis(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    entities: list[dict[str, Any]] = []
    for entity in raw.get("entities") or []:
        if not isinstance(entity, dict) or not entity.get("name"):
            continue
        name = slug(entity["name"])
        if not name or any(existing["name"] == name for existing in entities):
            continue
        fields = []
        for item in entity.get("fields") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            field_name = slug(item["name"])
            if not field_name or field_name == "id" or any(f["name"] == field_name for f in fields):
                continue
            field_type = item.get("type") if item.get("type") in FIELD_TYPES else "text"
            field = {"name": field_name, "label": str(item.get("label") or item["name"]), "type": field_type}
            if field_type == "enum":
                field["options"] = [str(option) for option in item.get("options") or []][:20]
            fields.append(field)
        if fields:
            entities.append({"name": name, "label": str(entity.get("label") or entity["name"]), "fields": fields})
    seed: dict[str, list[dict[str, Any]]] = {}
    raw_seed = raw.get("seed") if isinstance(raw.get("seed"), dict) else {}
    raw_seed = {slug(key): value for key, value in raw_seed.items()}
    for entity in entities:
        records = []
        types = {field["name"]: field["type"] for field in entity["fields"]}
        for index, record in enumerate(raw_seed.get(entity["name"]) or []):
            if not isinstance(record, dict):
                continue
            clean = {"id": str(record.get("id") or f"{entity['name']}_{index + 1}")}
            for key, value in record.items():
                key = slug(key)
                if key in types:
                    clean[key] = _coerce(value, types[key])
            records.append(clean)
        ids = [record["id"] for record in records]
        if len(set(ids)) != len(ids):
            for index, record in enumerate(records):
                record["id"] = f"{entity['name']}_{index + 1}"
        if not records:
            warnings.append(f"Aucune donnée de départ pour « {entity['label']} ».")
        seed[entity["name"]] = records[:30]
    profiles = [
        {"name": str(profile.get("name")), "description": str(profile.get("description") or "")}
        for profile in raw.get("profiles") or []
        if isinstance(profile, dict) and profile.get("name")
    ][:8]
    if not entities:
        warnings.append("Le modèle n’a proposé aucun objet métier exploitable.")
    return {"entities": entities, "seed": seed, "profiles": profiles}, warnings


def analyze_context(context: ContextDocument, screens: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    raw = complete_json(CONTEXT_SYSTEM, context_prompt(context, screens))
    return clean_analysis(raw)


# --- One screen → its behaviours -------------------------------------------------------

SCREEN_SYSTEM = (
    "Tu es un designer UX qui rend un prototype interactif pour des tests utilisateurs. Pour un écran, tu décris "
    "les règles des champs, l’effet des boutons et les données affichées, en t’appuyant sur la spécification et "
    "le parcours. Tu réponds uniquement avec un objet JSON valide, sans texte autour, et tu n’utilises que les "
    "identifiants de calques, d’écrans, d’entités et de champs fournis."
)


def screen_prompt(screen: dict[str, Any], root: dict[str, Any], spec: str | None, entities: list[dict[str, Any]],
                  screens: list[dict[str, Any]], context_excerpt: str = "") -> str:
    groups = repeat_groups(root)
    group_lines = "\n".join(
        f"- conteneur [{group['container']}] : {len(group['items'])} éléments répétés ; textes du premier : "
        + ", ".join(f"[{text['id']}] « {text['text'][:40]} »" for text in group["texts"])
        for group in groups
    ) or "- aucun"
    entity_lines = "\n".join(
        f"- {entity['name']} ({entity['label']}) : " + ", ".join(f"{field['name']} ({field['type']})" for field in entity["fields"])
        for entity in entities
    ) or "- aucune (laisse \"entity\" vide)"
    screen_lines = "\n".join(f"- {item['id']} : {item['name']}" for item in screens)
    link_lines = "\n".join(
        f"- « {link['label'] or 'sans libellé'} » → {link['target']}"
        + (" si " + " et ".join(f"{c['decision']} = {c['answer']}" for c in link["conditions"]) if link["conditions"] else "")
        for link in screen.get("links") or []
    ) or "- aucun"
    spec_text = (spec or "")[:MAX_SPEC_CHARS] or "(pas de spécification pour cet écran : ne déduis que ce qui est évident)"
    return f"""Écran : {screen['name']} (id {screen['id']})

Écrans du prototype :
{screen_lines}

Liens du parcours au départ de cet écran :
{link_lines}

Objets métier (entités et champs) :
{entity_lines}

Calques de l’écran (identifiant entre crochets) :
{outline(root)}

Éléments répétés (listes, cartes) :
{group_lines}
{f"{chr(10)}Contexte (extrait) :{chr(10)}{context_excerpt}{chr(10)}" if context_excerpt else ""}
Spécification de l’écran :
<<<
{spec_text}
>>>

Réponds avec ce JSON (tableaux vides si rien ne s’applique) :
{{
  "fields": [{{"node": "<id d’un calque INPUT>", "entity": "demande", "field": "montant", "required": true, "format": "number", "min": 0, "max": 500, "min_length": null, "max_length": null, "message": "Le montant ne peut pas dépasser 500 €."}}],
  "actions": [{{"node": "<id d’un calque BUTTON>", "type": "submit", "entity": "demande", "target": "<id d’écran>", "set": {{"statut": "En attente"}}, "branches": [{{"field": "montant", "op": ">", "value": 500, "target": "<id d’écran>"}}]}}],
  "lists": [{{"container": "<id d’un conteneur répété>", "entity": "demande", "fields": {{"<id d’un texte du premier élément>": "objet"}}, "target": "<id de l’écran de détail ou null>"}}],
  "bindings": [{{"node": "<id d’un TEXTE>", "entity": "demande", "field": "objet"}}]
}}

Règles :
- "fields" : un objet par calque INPUT. "format" parmi text, long_text, number, date, email, phone. "message" : le texte d’erreur affiché, en français, d’après la spec.
- "actions" : "type" parmi navigate (aller à "target"), submit (vérifie les champs de l’écran, enregistre l’objet puis va à "target"), delete, back, set (modifie des champs de l’objet courant, par exemple un statut). "branches" : destinations conditionnelles, d’après les décisions du parcours ; "op" parmi >, >=, <, <=, ==, !=, empty, not_empty.
- "lists" : pour afficher les données de départ à la place des exemples de la maquette ; "target" = écran ouvert au clic sur un élément.
- "bindings" : textes qui affichent l’objet courant (écran de détail, confirmation).
- N’utilise que les identifiants listés ci-dessus."""


def _ids(root: dict[str, Any]) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {"all": set(), "input": set(), "text": set(), "containers": set()}
    for node in iter_nodes(root):
        sets["all"].add(node["id"])
        if node.get("role") == "input":
            sets["input"].add(node["id"])
        if node.get("type") == "text":
            sets["text"].add(node["id"])
    return sets


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def clean_behaviors(raw: dict[str, Any], root: dict[str, Any], entities: list[dict[str, Any]],
                    screen_ids: set[str]) -> tuple[dict[str, Any], list[str]]:
    ids = _ids(root)
    groups = {group["container"]: group for group in repeat_groups(root)}
    entity_fields = {entity["name"]: {field["name"] for field in entity["fields"]} for entity in entities}
    dropped: list[str] = []

    def entity_field(entity: Any, field: Any) -> tuple[str | None, str | None]:
        entity_name = slug(entity) if entity else None
        if entity_name not in entity_fields:
            return None, None
        field_name = slug(field) if field else None
        return entity_name, field_name if field_name in entity_fields[entity_name] else None

    fields = {}
    for item in raw.get("fields") or []:
        if not isinstance(item, dict) or item.get("node") not in ids["input"]:
            dropped.append(f"règle de champ sur un calque inconnu ({item.get('node') if isinstance(item, dict) else item})")
            continue
        entity, field = entity_field(item.get("entity"), item.get("field"))
        rule = {
            "entity": entity,
            "field": field,
            "required": bool(item.get("required")),
            "format": item.get("format") if item.get("format") in FORMATS else "text",
            "message": str(item.get("message") or "")[:200],
        }
        for key in ("min", "max", "min_length", "max_length"):
            number = _number(item.get(key))
            if number is not None:
                rule[key] = number
        fields[item["node"]] = rule

    actions = {}
    for item in raw.get("actions") or []:
        if not isinstance(item, dict) or item.get("node") not in ids["all"] or item.get("type") not in ACTION_TYPES:
            dropped.append(f"action sur un calque inconnu ou de type inconnu ({item.get('node') if isinstance(item, dict) else item})")
            continue
        target = item.get("target") if item.get("target") in screen_ids else None
        if item["type"] == "navigate" and not target:
            dropped.append(f"navigation vers un écran inconnu ({item.get('target')})")
            continue
        entity, _ = entity_field(item.get("entity"), None)
        action: dict[str, Any] = {"type": item["type"], "target": target, "entity": entity}
        if isinstance(item.get("set"), dict) and entity:
            action["set"] = {slug(key): value for key, value in item["set"].items() if slug(key) in entity_fields[entity]}
        branches = []
        for branch in item.get("branches") or []:
            if not isinstance(branch, dict) or branch.get("op") not in OPERATORS or branch.get("target") not in screen_ids:
                continue
            branch_field = slug(branch.get("field") or "")
            if entity and branch_field not in entity_fields[entity]:
                continue
            branches.append({"field": branch_field, "op": branch["op"], "value": branch.get("value"), "target": branch["target"]})
        if branches:
            action["branches"] = branches
        actions[item["node"]] = action

    lists = {}
    for item in raw.get("lists") or []:
        if not isinstance(item, dict) or item.get("container") not in groups:
            dropped.append("liste sur un conteneur inconnu")
            continue
        entity, _ = entity_field(item.get("entity"), None)
        if not entity:
            dropped.append("liste sans objet métier connu")
            continue
        template_texts = {text["id"] for text in groups[item["container"]]["texts"]}
        mapping = {node: slug(field) for node, field in (item.get("fields") or {}).items() if node in template_texts and slug(field) in entity_fields[entity]}
        lists[item["container"]] = {
            "entity": entity,
            "template": groups[item["container"]]["template"],
            "items": groups[item["container"]]["items"],
            "fields": mapping,
            "target": item.get("target") if item.get("target") in screen_ids else None,
        }

    bindings = {}
    for item in raw.get("bindings") or []:
        if not isinstance(item, dict) or item.get("node") not in ids["text"]:
            continue
        entity, field = entity_field(item.get("entity"), item.get("field"))
        if entity and field:
            bindings[item["node"]] = {"entity": entity, "field": field}

    return {"fields": fields, "actions": actions, "lists": lists, "bindings": bindings}, dropped


def enrich_screen(screen: dict[str, Any], root: dict[str, Any], spec: str | None, entities: list[dict[str, Any]],
                  screens: list[dict[str, Any]], context_excerpt: str = "") -> tuple[dict[str, Any], list[str]]:
    raw = complete_json(SCREEN_SYSTEM, screen_prompt(screen, root, spec, entities, screens, context_excerpt))
    return clean_behaviors(raw, root, entities, {item["id"] for item in screens})
