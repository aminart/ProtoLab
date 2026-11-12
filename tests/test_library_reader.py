import pytest

from conftest import load_fixture
from library_reader import LibraryError, _upgrade, add_files, inventory, library_summary, merged_tokens, read_library, remove_file, theme_from


def test_variables_are_tokens_with_aliases_resolved():
    library = read_library(load_fixture("global_variables.json"), "variables.json")
    assert library["kind"] == "tokens"
    tokens = {token["name"]: token["value"] for token in library["tokens"]}
    assert tokens == {"color/primary": "#0D5E52", "color/error": "#D92E21", "red/600": "#D92E21", "spacing/md": 16}


def test_design_tokens_export():
    library = read_library({"color": {"brand": {"primary": {"$value": "#123456", "$type": "color"}}}, "font": {"family": {"$value": "Inter", "$type": "fontFamily"}}})
    assert library["kind"] == "tokens"
    assert {"name": "color/brand/primary", "type": "color", "value": "#123456", "collection": "color", "mode": ""} in library["tokens"]
    assert theme_from([library])["primary"] == "#123456"
    assert theme_from([library])["font"].startswith('"Inter"')


def test_components_of_a_library_file():
    library = read_library(load_fixture("global_components.json"), "ds.json")
    assert library["kind"] == "components"
    assert {(c["key"], c["set"], tuple(c["props"].items())) for c in library["components"]} == {
        ("key-input", "Input", (("State", "Default"),)), ("key-input-error", "Input", (("State", "Error"),)),
    }
    project = read_library(load_fixture("project_library.json"))
    assert project["tokens"] == [{"name": "Surface/Default", "type": "color", "value": "#FFFFFF", "collection": "Styles", "mode": ""}]


def test_a_library_is_a_list_of_files():
    library = add_files(None, [read_library(load_fixture("global_components.json"), "ds.json")])
    library = add_files(library, [read_library(load_fixture("global_variables.json"), "vars.json")])
    summary = library_summary(library)
    assert [(f["name"], f["kind"]) for f in summary["files"]] == [("ds.json", "components"), ("vars.json", "tokens")]
    assert summary["components"] == 2 and summary["tokens"] == 4
    library = add_files(library, [read_library({"color": {"primary": {"$value": "#000000"}}}, "vars.json")])
    assert [f["name"] for f in library_summary(library)["files"]] == ["ds.json", "vars.json"]
    assert library_summary(library)["tokens"] == 1
    assert remove_file(remove_file(library, library["files"][0]["id"]), library["files"][1]["id"]) is None


def test_aliases_resolve_across_files_and_libraries():
    foundations = read_library({"color": {"brand": {"primary": {"$value": "#123456"}}, "red": {"600": {"$value": "rgb(217, 45, 32)"}}}}, "colors.json")
    button = read_library({"button": {"primary": {"bg": {"$value": "{color.brand.primary}", "$type": "color"}}, "danger": {"bg": {"$value": "{color.red.600}"}}}}, "button.json")
    global_library = add_files(None, [foundations])
    project = add_files(None, [button])
    tokens, unresolved = merged_tokens([project, global_library])
    values = {t["name"]: t["value"] for t in tokens}
    assert values["button/primary/bg"] == "#123456" and values["button/danger/bg"] == "rgb(217, 45, 32)"
    assert unresolved == []
    assert merged_tokens([project])[1] == ["button/primary/bg", "button/danger/bg"]
    # Foundations win over component tokens for the theme.
    assert theme_from([project, global_library])["primary"] == "#123456"


def test_w3c_2025_colors():
    library = read_library({"brand": {"$type": "color", "main": {"$value": {"colorSpace": "srgb", "components": [1, 0, 0]}}}})
    assert library["tokens"][0]["value"] == "#FF0000"


def test_libraries_saved_by_0_1_0_are_upgraded():
    old = {"components": [{"key": "k", "name": "A"}], "tokens": [{"name": "c", "type": "color", "value": "#000000"}], "components_source": "ds.json", "tokens_source": "t.json", "style_tokens": []}
    assert [f["name"] for f in _upgrade(old)["files"]] == ["ds.json", "t.json"]
    assert library_summary(old)["components"] == 1


def test_unknown_file():
    with pytest.raises(LibraryError):
        read_library({"foo": "bar"})


def test_inventory_sources():
    rows = [{"key": "a", "remote": True, "name": "A"}, {"key": "b", "remote": True, "name": "B"}, {"key": "c", "remote": False, "name": "C"}, {"key": "d", "remote": True, "name": "D"}]
    result = inventory(rows, add_files(None, [{"kind": "components", "source": "p", "components": [{"key": "a"}], "tokens": []}]),
                       add_files(None, [{"kind": "components", "source": "g", "components": [{"key": "b"}], "tokens": []}]), set())
    assert [row["source"] for row in result["components"]] == ["project", "global", "local", "missing"]
