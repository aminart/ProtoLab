import json

from conftest import FIXTURES, load_fixture


def upload(client, path, name, content):
    key = "files" if "library" in path or "libraries" in path else "file"
    return client.post(path, files={key: (name, content.encode("utf-8") if isinstance(content, str) else content)})


def make_project(client, mockup, context_md, spec_md):
    project = client.post("/api/projects", json={"name": "Portail"}).json()
    pid = project["id"]
    assert upload(client, f"/api/projects/{pid}/context", "contexte.md", context_md).status_code == 200
    assert upload(client, f"/api/projects/{pid}/specs", "spec-nouvelle-demande.md", spec_md).status_code == 200
    assert upload(client, f"/api/projects/{pid}/figma", "maquette.json", json.dumps(mockup)).status_code == 200
    return pid


def test_project_flow(client, mockup, context_md, spec_md):
    pid = make_project(client, mockup, context_md, spec_md)
    overview = client.get(f"/api/projects/{pid}").json()
    assert overview["context"]["screens"] == 5 and overview["context"]["modules"] == 2
    assert overview["specs"][0]["screen"] == "Nouvelle demande"
    assert overview["figma"]["frames"] == 4 and overview["figma"]["page_id"] == "0:2"
    assert any(p["id"] == pid for p in client.get("/api/projects").json())

    structure = client.get(f"/api/projects/{pid}/structure").json()
    assert structure["start"] == "ecran_connexion"
    assert {s["id"]: s["frame_name"] for s in structure["screens"]}["ecran_nouvelle"] == "Nouvelle demande v2"

    structure = client.put(f"/api/projects/{pid}/screens/figma_1_4", json={"excluded": True}).json()
    assert next(s for s in structure["screens"] if s["id"] == "figma_1_4")["excluded"]
    structure = client.put(f"/api/projects/{pid}/screens/ecran_confirmation", json={"frame": "1:4"}).json()
    assert next(s for s in structure["screens"] if s["id"] == "ecran_confirmation")["frame"] == "1:4"
    structure = client.put(f"/api/projects/{pid}/screens/ecran_confirmation", json={"frame": "auto"}).json()
    assert next(s for s in structure["screens"] if s["id"] == "ecran_confirmation")["frame"] is None

    model = client.get(f"/api/projects/{pid}/prototype").json()
    assert [s["id"] for s in model["screens"]][:2] == ["ecran_connexion", "ecran_mot_de_passe"]


def test_bad_uploads(client):
    pid = client.post("/api/projects", json={"name": "X"}).json()["id"]
    assert upload(client, f"/api/projects/{pid}/figma", "x.json", "pas du json").status_code == 422
    assert upload(client, f"/api/projects/{pid}/figma", "x.json", json.dumps({"a": 1})).status_code == 422
    assert upload(client, f"/api/projects/{pid}/library", "x.json", json.dumps({"a": 1})).status_code == 422
    assert client.get("/api/projects/inconnu").status_code == 404
    assert client.get("/api/projects/bad..id/structure").status_code == 404
    assert client.get("/api/inconnue").status_code == 404


def test_libraries(client, mockup, context_md, spec_md):
    pid = make_project(client, mockup, context_md, spec_md)
    overview = upload(client, f"/api/projects/{pid}/library", "lib.json", (FIXTURES / "project_library.json").read_text()).json()
    assert overview["library"]["components"] == 1
    assert overview["library"]["inventory"] == {"project": 1, "global": 0, "local": 0, "missing": 2}
    upload(client, "/api/libraries/global", "ds.json", (FIXTURES / "global_components.json").read_text())
    summary = upload(client, "/api/libraries/global", "vars.json", (FIXTURES / "global_variables.json").read_text()).json()["library"]
    assert summary["components"] == 2 and summary["tokens"] == 4
    assert [f["name"] for f in summary["files"]] == ["ds.json", "vars.json"]
    overview = client.get(f"/api/projects/{pid}").json()
    assert overview["library"]["inventory"]["global"] == 1
    assert client.get(f"/api/projects/{pid}/prototype").json()["theme"]["primary"] == "#0D5E52"
    client.delete("/api/libraries/global")
    assert client.get("/api/libraries/global").json() is None


def test_analyze_and_enrich_with_the_model(client, fake_llm, mockup, context_md, spec_md):
    pid = make_project(client, mockup, context_md, spec_md)
    fake_llm.queue({
        "entities": [{"name": "demande", "label": "Demande", "fields": [{"name": "objet", "type": "text"}, {"name": "montant", "type": "number"}, {"name": "statut", "type": "text"}]}],
        "seed": {"demande": [{"id": "d1", "objet": "Licences", "montant": 300, "statut": "Validée"}]},
        "profiles": [{"name": "Demandeur"}],
    })
    body = client.post(f"/api/projects/{pid}/analyze").json()
    assert body["analysis"]["entities"] == [{"name": "demande", "label": "Demande", "fields": 3, "records": 1}]
    assert "Montant > 500" not in fake_llm.user_prompt(0)  # the diagram is not sent, only the text
    assert "Les salariés déposent des demandes" in fake_llm.user_prompt(0)

    model = client.get(f"/api/projects/{pid}/prototype").json()
    nouvelle = next(s for s in model["screens"] if s["id"] == "ecran_nouvelle")
    inputs = [n["id"] for n in _nodes(nouvelle["root"]) if n.get("role") == "input"]
    fake_llm.queue("Voici le JSON :\n```json\n" + json.dumps({"fields": [{"node": inputs[1], "entity": "demande", "field": "montant", "required": True, "format": "number"}]}) + "\n```")
    body = client.post(f"/api/projects/{pid}/screens/ecran_nouvelle/enrich").json()
    assert body["counts"]["fields"] == 1
    assert "Indiquez le montant" in fake_llm.user_prompt(1)
    model = client.get(f"/api/projects/{pid}/prototype").json()
    nouvelle = next(s for s in model["screens"] if s["id"] == "ecran_nouvelle")
    assert nouvelle["behaviors"]["fields"][inputs[1]]["format"] == "number"
    assert model["seed"]["demande"][0]["objet"] == "Licences"

    assert client.post(f"/api/projects/{pid}/screens/ecran_confirmation/enrich").status_code == 400


def test_model_answer_that_is_not_json_is_asked_again(client, fake_llm, mockup, context_md, spec_md):
    pid = make_project(client, mockup, context_md, spec_md)
    fake_llm.queue("désolé", "toujours pas")
    assert client.post(f"/api/projects/{pid}/analyze").status_code == 502
    assert len(fake_llm.calls) == 2


def test_versions_and_export(client, mockup, context_md, spec_md, monkeypatch, tmp_path):
    import export_html

    pid = make_project(client, mockup, context_md, spec_md)
    version = client.post(f"/api/projects/{pid}/versions", json={"label": "Test du 12"}).json()
    assert version["label"] == "Test du 12" and version["screens"] == 6
    frozen = client.get(f"/api/projects/{pid}/versions/{version['id']}").json()
    assert frozen["version"]["id"] == version["id"]
    # Later changes do not touch the frozen version.
    client.put(f"/api/projects/{pid}/screens/ecran_liste", json={"excluded": True})
    assert any(s["id"] == "ecran_liste" for s in client.get(f"/api/projects/{pid}/versions/{version['id']}").json()["screens"])

    bundle = tmp_path / "player.js"
    bundle.write_text("console.log('</script>');")
    monkeypatch.setattr(export_html, "player_bundle", lambda: bundle)
    response = client.get(f"/api/projects/{pid}/export", params={"version": version["id"]})
    assert response.status_code == 200
    assert 'filename="portail-test-du-12.html"' in response.headers["content-disposition"]
    assert "window.__PROTOLAB_MODEL__" in response.text and "<\\/script>" in response.text
    assert response.text.count("</script>") == 2

    assert client.delete(f"/api/projects/{pid}/versions/{version['id']}").json() == []
    assert client.get(f"/api/projects/{pid}/versions/{version['id']}").status_code == 404


def _nodes(node):
    yield node
    for child in node.get("children") or []:
        yield from _nodes(child)


def test_many_token_files_zip_and_errors(client):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("tokens/foundations/colors.json", json.dumps({"color": {"brand": {"primary": {"$value": "#0D5E52", "$type": "color"}}}}))
        archive.writestr("tokens/components/button.json", json.dumps({"button": {"primary": {"background": {"$value": "{color.brand.primary}", "$type": "color"}}}}))
        archive.writestr("__MACOSX/._colors.json", "binaire")
        archive.writestr("lisez-moi.txt", "ignoré")
    files = [
        ("files", ("ds.zip", buffer.getvalue())),
        ("files", ("tokens/components/input.json", json.dumps({"input": {"border": {"error": {"$value": "{color.feedback.error}"}}}}).encode())),
        ("files", ("notes.json", b'{"hello": "world"}')),
    ]
    body = client.post("/api/libraries/global", files=files).json()
    assert [f["name"] for f in body["library"]["files"]] == ["tokens/foundations/colors.json", "tokens/components/button.json", "tokens/components/input.json"]
    assert body["import_errors"][0]["file"] == "notes.json"
    assert body["library"]["unresolved"] == ["input/border/error"]
    tokens = {t["name"]: t["value"] for t in body["library"]["tokens_list"]}
    assert tokens["button/primary/background"] == "#0D5E52"

    # Re-importing a file of the same name replaces it; a file can be removed alone.
    body = client.post("/api/libraries/global", files=[("files", ("tokens/components/input.json", json.dumps({"input": {"border": {"error": {"$value": "#D92D20"}}}}).encode()))]).json()
    assert len(body["library"]["files"]) == 3 and body["library"]["unresolved"] == []
    file_id = body["library"]["files"][0]["id"]
    library = client.delete(f"/api/libraries/global/files/{file_id}").json()
    assert len(library["files"]) == 2
    assert library["unresolved"] == ["button/primary/background"]

    assert client.post("/api/libraries/global", files=[("files", ("x.json", b"{}"))]).status_code == 422
    client.delete("/api/libraries/global")
