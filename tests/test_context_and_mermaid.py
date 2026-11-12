import pytest

from context_reader import read_context
from mermaid_reader import MermaidError, read_mermaid
from structure_builder import build_structure


def test_context_sections_and_main_diagram(context_md):
    document = read_context(context_md)
    assert document.title == "Portail des demandes"
    assert [s.title for s in document.sections if s.level == 2] == ["Contexte métier", "Profils", "Structure de l'app", "Fonctionnalités"]
    assert len(document.mermaid) == 1
    assert document.main_diagram().section_path == ["Portail des demandes", "Structure de l'app"]
    assert "flowchart" not in document.text_without_diagrams()


def test_main_diagram_prefers_structure_section():
    markdown = "# App\n## Parcours achat\n```mermaid\nsequenceDiagram\nA->>B: x\n```\n## Annexe\n```mermaid\ngraph LR\nA-->B-->C-->D\n```\n## Structure\n```mermaid\nflowchart TD\nx[Accueil]-->y[Profil]\n```\n"
    assert "Accueil" in read_context(markdown).main_diagram().code


def test_node_kinds_from_shapes_and_classes():
    graph = read_mermaid("""graph LR
      a[Écran A] --> b{Choix ?}
      b -->|oui| c(Envoi du mail)
      b -- non --> d([Fin])
      e[[Traitement]]:::screen
      class c screen
    """)
    kinds = {node.id: node.kind for node in graph.nodes.values()}
    assert kinds == {"a": "screen", "b": "decision", "c": "screen", "d": "action", "e": "screen"}
    assert [(e["source"], e["target"], e["label"]) for e in graph.edges] == [("a", "b", ""), ("b", "c", "oui"), ("b", "d", "non")]


def test_labels_are_cleaned():
    graph = read_mermaid('flowchart TD\n  a["Mot de passe<br/>**oublié**"] -.->|"Retour #quot;ok#quot;"| b[Accueil];')
    assert graph.nodes["a"].label == "Mot de passe oublié"
    assert graph.edges[0]["label"] == 'Retour "ok"'
    assert graph.edges[0]["dotted"]


def test_groups_chains_and_subgraphs():
    graph = read_mermaid("""flowchart TD
      subgraph m1 [Module un]
        a[A] & b[B] --> c[C] --> d[D]
      end
      subgraph "Module deux"
        e[E]
      end
      d --> e
    """)
    assert len(graph.edges) == 4
    assert graph.nodes["a"].subgraph == "m1"
    assert graph.subgraphs["module_deux"]["title"] == "Module deux"
    assert graph.nodes["e"].subgraph == "module_deux"


def test_not_a_flowchart():
    with pytest.raises(MermaidError):
        read_mermaid("sequenceDiagram\nA->>B: hello")


def test_structure_goes_through_decisions_and_actions(context_md):
    structure = build_structure(read_mermaid(read_context(context_md).main_diagram().code))
    screens = {screen["id"]: screen for screen in structure["screens"]}
    assert structure["start"] == "ecran_connexion"
    assert [m["title"] for m in structure["modules"]] == ["Accès", "Demandes"]
    links = screens["ecran_nouvelle"]["links"]
    assert {(l["target"], l["label"], l["conditions"][0]["answer"]) for l in links} == {
        ("ecran_confirmation", "Envoyer", "Oui"),
        ("ecran_confirmation", "Envoyer", "Non"),
    }
    assert next(l for l in links if l["conditions"][0]["answer"] == "Oui")["via"] == ["Notification du manager"]
    assert structure["decisions"] == ["Montant > 500 € ?"]
