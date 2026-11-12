import pytest

from conftest import load_fixture
from library_reader import LibraryError, inventory, merge_library, read_library, theme_from


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


def test_merge_keeps_one_file_of_each_kind():
    merged = merge_library(None, read_library(load_fixture("global_components.json"), "ds.json"))
    merged = merge_library(merged, read_library(load_fixture("global_variables.json"), "vars.json"))
    assert merged["components_source"] == "ds.json" and merged["tokens_source"] == "vars.json"
    assert len(merged["components"]) == 2 and len(merged["tokens"]) == 4


def test_unknown_file():
    with pytest.raises(LibraryError):
        read_library({"foo": "bar"})


def test_inventory_sources():
    rows = [{"key": "a", "remote": True, "name": "A"}, {"key": "b", "remote": True, "name": "B"}, {"key": "c", "remote": False, "name": "C"}, {"key": "d", "remote": True, "name": "D"}]
    result = inventory(rows, {"components": [{"key": "a"}]}, {"components": [{"key": "b"}]}, set())
    assert [row["source"] for row in result["components"]] == ["project", "global", "local", "missing"]
