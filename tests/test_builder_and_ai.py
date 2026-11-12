from ai_enrichment import clean_analysis, clean_behaviors, screen_prompt
from conftest import load_fixture
from figma_reader import iter_nodes
from library_reader import merge_library, read_library
from prototype_builder import _key, assemble, build_model


def project(**extra):
    return {"name": "Portail", "specs": [{"id": "s1", "name": "spec-nouvelle-demande.md"}], "figma": {}, "library": None, "overrides": {}, **extra}


def test_names_are_compared_without_noise():
    assert _key("01 - Écran Connexion v2") == "connexion"
    assert _key("Nouvelle demande – copie") == "nouvelle demande"


def test_frames_and_specs_are_matched_to_the_flow(mockup, context_md, spec_md):
    result = assemble(project(), context_md, {"s1": spec_md}, mockup, None)
    by_id = {screen["id"]: screen for screen in result.screens}
    assert by_id["ecran_connexion"]["frame"] == "1:1"
    assert by_id["ecran_nouvelle"]["frame"] == "1:3" and by_id["ecran_nouvelle"]["spec"] == "s1"
    assert by_id["ecran_confirmation"]["kind"] == "deduced"
    assert by_id["figma_1_4"]["kind"] == "figma_only"
    assert result.start == "ecran_connexion"
    messages = " ".join(w["message"] for w in result.warnings)
    assert "Mot de passe oublié, Confirmation" in messages and "Bandeau d'aide" in messages


def test_overrides_win(mockup, context_md, spec_md):
    overrides = {"screens": {"ecran_confirmation": {"frame": "1:4"}, "ecran_nouvelle": {"spec": "none"}, "ecran_mot_de_passe": {"excluded": True}}, "start": "ecran_liste"}
    result = assemble(project(overrides=overrides), context_md, {"s1": spec_md}, mockup, None)
    by_id = {screen["id"]: screen for screen in result.screens}
    assert by_id["ecran_confirmation"]["frame"] == "1:4"
    assert "figma_1_4" not in by_id
    assert by_id["ecran_nouvelle"]["spec"] is None
    model = build_model(project(overrides=overrides), result, None)
    assert "ecran_mot_de_passe" not in {s["id"] for s in model["screens"]}
    assert model["start"] == "ecran_liste"


def test_model_navigation_points_to_screens(mockup, context_md):
    result = assemble(project(), context_md, {}, mockup, None)
    model = build_model(project(), result, None)
    screens = {screen["id"]: screen for screen in model["screens"]}
    login_button = next(n for n in iter_nodes(screens["ecran_connexion"]["root"]) if n.get("role") == "button")
    assert login_button["nav"]["screen"] == "ecran_liste"
    # No Figma link, but its text is the label of the flow's link.
    new_button = next(n for n in iter_nodes(screens["ecran_liste"]["root"]) if n.get("role") == "button")
    assert new_button["nav"] == {"kind": "navigate", "screen": "ecran_nouvelle", "from_flow": True}
    assert screens["ecran_confirmation"]["root"] is None and screens["ecran_confirmation"]["width"] == 390
    assert model["modules"][0]["title"] == "Accès"


def test_theme_comes_from_the_libraries(mockup, context_md):
    library = merge_library(None, read_library(load_fixture("global_variables.json")))
    model = build_model(project(), assemble(project(), context_md, {}, mockup, library), library)
    assert model["theme"]["primary"] == "#0D5E52" and model["theme"]["danger"] == "#D92E21"


def test_clean_analysis():
    analysis, warnings = clean_analysis({
        "entities": [{"name": "Demande d'achat", "label": "Demande", "fields": [
            {"name": "Montant", "type": "number"}, {"name": "statut", "type": "enum", "options": ["A", "B"]}, {"name": "id"}, {"name": "x", "type": "bizarre"}]}],
        "seed": {"demande_d_achat": [{"montant": "1 200,5", "statut": "A", "inconnu": 1}, {"id": "z", "montant": 3}]},
    })
    entity = analysis["entities"][0]
    assert entity["name"] == "demande_d_achat"
    assert [f["name"] for f in entity["fields"]] == ["montant", "statut", "x"]
    assert entity["fields"][2]["type"] == "text"
    assert analysis["seed"]["demande_d_achat"] == [{"id": "demande_d_achat_1", "montant": 1200.5, "statut": "A"}, {"id": "z", "montant": 3}]
    assert not warnings


ENTITIES = [{"name": "demande", "label": "Demande", "fields": [{"name": "objet", "type": "text"}, {"name": "montant", "type": "number"}, {"name": "statut", "type": "text"}]}]


def screen_roots(mockup, context_md):
    result = assemble(project(), context_md, {}, mockup, None)
    return result, {screen["id"]: result.roots.get(screen["frame"] or "") for screen in result.screens}


def test_clean_behaviors_keeps_only_known_ids(mockup, context_md):
    _, roots = screen_roots(mockup, context_md)
    root = roots["ecran_nouvelle"]
    inputs = [n["id"] for n in iter_nodes(root) if n.get("role") == "input"]
    button = next(n["id"] for n in iter_nodes(root) if n.get("role") == "button")
    behaviors, dropped = clean_behaviors({
        "fields": [{"node": inputs[1], "entity": "demande", "field": "montant", "required": True, "format": "number", "max": "5000", "message": "Trop cher"},
                   {"node": "9:99", "entity": "demande", "field": "objet"}],
        "actions": [{"node": button, "type": "submit", "entity": "demande", "target": "ecran_confirmation", "set": {"statut": "En attente", "pirate": 1},
                     "branches": [{"field": "montant", "op": ">", "value": 500, "target": "ecran_confirmation"}, {"field": "montant", "op": "~", "target": "x"}]},
                    {"node": button, "type": "navigate", "target": "nulle_part"}],
    }, root, ENTITIES, {"ecran_confirmation", "ecran_liste"})
    rule = behaviors["fields"][inputs[1]]
    assert rule == {"entity": "demande", "field": "montant", "required": True, "format": "number", "message": "Trop cher", "max": 5000.0}
    assert behaviors["actions"][button]["set"] == {"statut": "En attente"}
    assert len(behaviors["actions"][button]["branches"]) == 1
    assert len(dropped) == 2


def test_lists_and_bindings(mockup, context_md):
    _, roots = screen_roots(mockup, context_md)
    root = roots["ecran_liste"]
    behaviors, _ = clean_behaviors({
        "lists": [{"container": "1:31", "entity": "demande", "fields": {"1:22": "objet", "1:23": "montant", "1:99": "objet"}, "target": "ecran_nouvelle"}],
        "bindings": [{"node": "1:21", "entity": "demande", "field": "objet"}, {"node": "1:21", "entity": "demande", "field": "nope"}],
    }, root, ENTITIES, {"ecran_nouvelle"})
    assert behaviors["lists"]["1:31"]["fields"] == {"1:22": "objet", "1:23": "montant"}
    assert behaviors["lists"]["1:31"]["items"] == ["1:24", "1:27", "1:30"]
    assert behaviors["bindings"] == {"1:21": {"entity": "demande", "field": "objet"}}


def test_screen_prompt_is_compact(mockup, context_md, spec_md):
    result, roots = screen_roots(mockup, context_md)
    screen = next(s for s in result.screens if s["id"] == "ecran_nouvelle")
    prompt = screen_prompt(screen, roots["ecran_nouvelle"], spec_md, ENTITIES, [{"id": s["id"], "name": s["name"]} for s in result.screens])
    assert "« Envoyer » → ecran_confirmation si Montant > 500 € ? = Oui" in prompt
    assert "Indiquez le montant de la demande" in prompt
    assert "demande (Demande) : objet (text), montant (number)" in prompt
    assert len(prompt) < 8000
