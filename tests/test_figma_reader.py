import pytest

from figma_reader import (
    Converter, FigmaError, convert_screen, css_color, default_page_id, fill_style, iter_nodes, list_pages, load_figma, outline, repeat_groups,
)


def screens(mockup):
    figma = load_figma(mockup)
    page = next(p for p in list_pages(figma) if p["id"] == default_page_id(list_pages(figma)))
    converter = Converter(figma)
    return {frame["id"]: convert_screen(converter, frame) for frame in page["_frames"]}, converter.report


def find(root, name):
    return next(node for node in iter_nodes(root) if node.get("name") == name)


def test_accepts_file_nodes_and_single_node(mockup):
    assert len(load_figma(mockup).roots) == 1
    nodes = {"name": "x", "nodes": {"1:1": {"document": mockup["document"]["children"][1]["children"][0], "components": mockup["components"]}}}
    figma = load_figma(nodes)
    assert figma.components["c:input"]["key"] == "key-input"
    assert list_pages(figma)[0]["frames"][0]["name"] == "01 - Connexion"
    assert list_pages(load_figma(mockup["document"]["children"][1]["children"][0]))[0]["frames"][0]["id"] == "1:1"
    with pytest.raises(FigmaError):
        load_figma({"hello": 1})


def test_prototype_page_is_chosen_by_default(mockup):
    pages = list_pages(load_figma(mockup))
    assert [p["name"] for p in pages] == ["Brouillons", "🟢 Prototype"]
    assert default_page_id(pages) == "0:2"
    assert len(pages[1]["frames"]) == 4


def test_auto_layout_becomes_flexbox(mockup):
    roots, _ = screens(mockup)
    root = roots["1:1"]
    assert root["style"]["width"] == "390px" and root["style"]["minHeight"] == "844px"
    assert root["style"]["flexDirection"] == "column"
    assert root["style"]["padding"] == "32px 24px 32px 24px"
    assert root["style"]["rowGap"] == "16px"
    button = find(root, "Button")
    assert button["style"]["justifyContent"] == "center" and button["style"]["alignItems"] == "center"
    assert "width" not in button["style"]  # hugs its label
    field = find(root, "Field")
    assert field["style"]["boxShadow"] == "inset 0 0 0 1px #CCD1D9"
    assert field["style"]["borderRadius"] == "6px"


def test_fill_stretch_and_hug_children():
    figma = load_figma({"id": "1", "type": "FRAME", "name": "F", "absoluteBoundingBox": {"x": 0, "y": 0, "width": 300, "height": 100},
                        "layoutMode": "HORIZONTAL", "children": [
                            {"id": "2", "type": "FRAME", "name": "grow", "absoluteBoundingBox": {"x": 0, "y": 0, "width": 100, "height": 40}, "layoutSizingHorizontal": "FILL", "layoutSizingVertical": "FILL"},
                            {"id": "3", "type": "FRAME", "name": "fixed", "absoluteBoundingBox": {"x": 100, "y": 0, "width": 80, "height": 40}, "layoutSizingHorizontal": "FIXED", "layoutSizingVertical": "HUG"},
                            {"id": "4", "type": "FRAME", "name": "abs", "absoluteBoundingBox": {"x": 250, "y": 10, "width": 20, "height": 20}, "layoutPositioning": "ABSOLUTE"},
                        ]})
    root = convert_screen(Converter(figma), figma.roots[0])
    grow, fixed, absolute = root["children"]
    assert grow["style"]["flex"] == "1 1 0px" and grow["style"]["alignSelf"] == "stretch"
    assert fixed["style"]["width"] == "80px" and "height" not in fixed["style"]
    assert absolute["style"]["position"] == "absolute" and absolute["style"]["left"] == "250px" and absolute["style"]["top"] == "10px"
    assert root["style"]["position"] == "relative"


def test_texts_vectors_images_and_report(mockup):
    roots, report = screens(mockup)
    title = find(roots["1:1"], "Titre")
    assert title["type"] == "text" and title["text"] == "Portail des demandes"
    assert title["style"]["fontSize"] == "24px" and title["style"]["fontWeight"] == "700"
    icon = find(roots["1:3"], "Icône")
    assert icon["type"] == "svg" and icon["paths"][0]["d"].startswith("M2") and icon["viewBox"] == "0 0 24 24"
    assert find(roots["1:4"], "Illustration")["image"] is True
    assert report.images == 1
    assert [zone["screen"] for zone in report.absolute_zones] == ["Bandeau d'aide"]
    assert {item["name"]: item["count"] for item in report.as_dict()["instances"]} == {"Input": 4, "Carte demande": 3, "Button": 3}


def test_roles_and_input_parts(mockup):
    roots, _ = screens(mockup)
    inputs = [node for node in iter_nodes(roots["1:3"]) if node.get("role") == "input"]
    assert len(inputs) == 2
    assert inputs[0]["input"]["label"] == "Objet"
    assert inputs[0]["input"]["placeholder"] == "Ex. : achat de matériel"
    assert inputs[0]["input"]["box"] == find(inputs[0], "Field")["id"]
    assert find(roots["1:3"], "Button")["role"] == "button"


def test_interactions(mockup):
    roots, report = screens(mockup)
    assert find(roots["1:1"], "Button")["nav"] == {"kind": "navigate", "frame": "1:2", "overlay": False}
    assert find(roots["1:3"], "Retour")["nav"] == {"kind": "back"}
    assert report.interactions == 5


def test_colors_and_fills():
    assert css_color({"r": 1, "g": 0, "b": 0, "a": 1}) == "#FF0000"
    assert css_color({"r": 0, "g": 0, "b": 0, "a": 1}, 0.5) == "rgba(0, 0, 0, 0.5)"
    style, image = fill_style([{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}, {"type": "GRADIENT_LINEAR", "gradientHandlePositions": [{"x": 0, "y": 0}, {"x": 0, "y": 1}],
                                "gradientStops": [{"color": {"r": 0, "g": 0, "b": 0, "a": 1}, "position": 0}, {"color": {"r": 1, "g": 1, "b": 1, "a": 1}, "position": 1}]}])
    assert style["backgroundImage"].startswith("linear-gradient(180.0deg, #000000 0.0%")
    assert style["backgroundImage"].endswith("linear-gradient(#FFFFFF, #FFFFFF)")
    assert not image


def test_outline_and_repeat_groups(mockup):
    roots, _ = screens(mockup)
    text = outline(roots["1:3"])
    assert "INPUT composant « Input »" in text and "libellé « Objet »" in text
    assert "Placeholder" not in text  # the inside of a field is not listed
    groups = repeat_groups(roots["1:2"])
    assert len(groups) == 1 and len(groups[0]["items"]) == 3
    assert [t["text"] for t in groups[0]["texts"]] == ["Achat de licences", "320 €"]
