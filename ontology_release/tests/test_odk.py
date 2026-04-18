from __future__ import annotations

import csv

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef

from aimworks_ontology_release.odk import (
    _build_ci_reproducibility_report,
    _build_actual_imports_report,
    _build_parity_report,
    _custom_makefile,
    _promotion_gates,
    _write_import_term_files,
)


H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")


def test_custom_makefile_overrides_base_rule_for_w3id_namespace():
    makefile = _custom_makefile({"sources": [{"id": "dcterms", "enabled": True}, {"id": "emmo-core", "enabled": True}]})
    assert "H2KG_LOCAL_BASE_IRI := https://w3id.org/h2kg/hydrogen-ontology" in makefile
    assert "$(ONT)-base.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(IMPORT_FILES)" in makefile
    assert "--base-iri $(H2KG_LOCAL_BASE_IRI)" in makefile
    assert "--base-iri $(H2KG_LOCAL_BASE_IRI)#" in makefile
    assert "--copy-ontology-annotations false" in makefile
    assert "<owl:AnnotationProperty rdf:about=\\\"$$term\\\"/>" in makefile
    assert '[ ! -s $(IMPORTDIR)/dcterms_terms.txt ] && [ "$(DCTERMS_REQUIRED)" != "true" ]' in makefile


def test_custom_makefile_strips_imports_for_qudt_vocab_mirrors():
    makefile = _custom_makefile({"sources": [{"id": "qudt-units", "enabled": True}, {"id": "qudt-quantitykinds", "enabled": True}]})
    assert "remove --input $(TMPDIR)/$@.raw.owl --select imports --trim false --output $(TMPDIR)/$@.owl" in makefile


def test_custom_makefile_uses_class_declarations_for_chebi_fallback():
    makefile = _custom_makefile({"sources": [{"id": "chebi", "enabled": True}]})
    assert "<owl:Class rdf:about=\\\"$$term\\\"/>" in makefile


def test_parity_report_ignores_extra_non_schema_local_terms_in_base_artifact(tmp_path):
    current = Graph()
    current.add((H2KG.Parameter, RDF.type, OWL.Class))
    current.add((H2KG.Property, RDF.type, OWL.Class))
    current.add((H2KG.hasParameter, RDF.type, OWL.ObjectProperty))
    current.add((H2KG.Parameter, RDFS.label, Literal("Parameter")))

    base = Graph()
    for triple in current:
        base.add(triple)
    base.add((H2KG.AssemblyTorque, RDF.type, H2KG.Parameter))
    base.add((H2KG.HotPlate, RDF.type, H2KG.Instrument))

    current_path = tmp_path / "current.ttl"
    base_path = tmp_path / "base.ttl"
    current.serialize(current_path, format="turtle")
    base.serialize(base_path, format="turtle")

    report = _build_parity_report(current_path, base_path)
    assert report["status"] == "aligned"
    assert report["iri_drift"] is False
    assert report["comparison_target"] == "base_artifact"
    assert report["artifact_incomplete"] is False
    assert report["actual_artifact_local_term_count"] == 5


def test_write_import_term_files_populates_source_specific_terms(tmp_path):
    project_root = tmp_path / "ontology_release"
    review_dir = project_root / "output" / "review"
    imports_dir = project_root / "odk" / "src" / "ontology" / "imports"
    review_dir.mkdir(parents=True)
    imports_dir.mkdir(parents=True)

    rows = [
        {
            "local_iri": str(H2KG.AssemblyTorque),
            "local_label": "Assembly Torque",
            "local_kind": "controlled_vocabulary_term",
            "relation": "skos:closeMatch",
            "target_iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_123",
            "target_label": "Electrochemistry thing",
            "target_kind": "class",
            "source": "emmo-electrochemistry",
            "score": "0.9",
            "status": "proposed",
            "rationale": "test",
        },
        {
            "local_iri": str(H2KG.HotPlate),
            "local_label": "Hot Plate",
            "local_kind": "controlled_vocabulary_term",
            "relation": "skos:closeMatch",
            "target_iri": "https://purls.helmholtz-metadaten.de/hob/HDO_00006003",
            "target_label": "HDO thing",
            "target_kind": "class",
            "source": "hdo",
            "score": "0.9",
            "status": "proposed",
            "rationale": "test",
        },
        {
            "local_iri": str(H2KG.Parameter),
            "local_label": "Parameter",
            "local_kind": "class",
            "relation": "skos:closeMatch",
            "target_iri": "http://www.w3.org/ns/prov#Agent",
            "target_label": "Agent",
            "target_kind": "class",
            "source": "hdo",
            "score": "0.1",
            "status": "proposed",
            "rationale": "should be filtered",
        },
    ]
    with (review_dir / "mapping_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    source_registry = {
        "sources": [
            {"id": "emmo-electrochemistry", "enabled": True, "remote_url": "https://w3id.org/emmo/domain/electrochemistry"},
            {"id": "hdo", "enabled": True, "source_iri": "https://purls.helmholtz-metadaten.de/hob/HDO_00000000"},
            {"id": "prov-o", "enabled": True, "remote_url": "http://www.w3.org/ns/prov#"},
        ]
    }

    _write_import_term_files(project_root, imports_dir, source_registry)

    assert (imports_dir / "emmo-electrochemistry_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_123"
    ]
    assert (imports_dir / "hdo_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "https://purls.helmholtz-metadaten.de/hob/HDO_00006003"
    ]
    assert (imports_dir / "prov-o_terms.txt").read_text(encoding="utf-8") == ""


def test_write_import_term_files_merges_graph_references_by_best_source_match(tmp_path):
    project_root = tmp_path / "ontology_release"
    review_dir = project_root / "output" / "review"
    imports_dir = project_root / "odk" / "src" / "ontology" / "imports"
    input_dir = project_root / "input"
    review_dir.mkdir(parents=True)
    imports_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)
    (review_dir / "mapping_review.csv").write_text(
        "local_iri,local_label,local_kind,relation,target_iri,target_label,target_kind,source,score,status,rationale\n",
        encoding="utf-8",
        newline="\n",
    )

    graph = Graph()
    graph.add((H2KG.Sample, RDF.type, URIRef("http://qudt.org/schema/qudt/QuantityValue")))
    graph.add((H2KG.Sample, URIRef("http://qudt.org/schema/qudt/unit"), URIRef("http://qudt.org/vocab/unit/DEG_C")))
    graph.add((H2KG.Sample, URIRef("http://qudt.org/schema/qudt/quantityKind"), URIRef("http://qudt.org/vocab/quantitykind/Temperature")))
    graph.add((H2KG.Sample, RDF.type, URIRef("https://w3id.org/emmo/domain/electrochemistry#electrochemistry_123")))
    graph.serialize(input_dir / "current_ontology.jsonld", format="json-ld")

    source_registry = {
        "sources": [
            {"id": "emmo-core", "enabled": True, "remote_url": "https://w3id.org/emmo"},
            {"id": "emmo-electrochemistry", "enabled": True, "remote_url": "https://w3id.org/emmo/domain/electrochemistry"},
            {"id": "qudt-schema", "enabled": True, "remote_url": "http://qudt.org/2.1/schema/qudt"},
            {"id": "qudt-units", "enabled": True, "remote_url": "http://qudt.org/2.1/vocab/unit"},
            {"id": "qudt-quantitykinds", "enabled": True, "remote_url": "http://qudt.org/2.1/vocab/quantitykind"},
        ]
    }

    _write_import_term_files(project_root, imports_dir, source_registry)

    assert (imports_dir / "qudt-schema_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "http://qudt.org/schema/qudt/QuantityValue",
        "http://qudt.org/schema/qudt/quantityKind",
        "http://qudt.org/schema/qudt/unit",
    ]
    assert (imports_dir / "qudt-units_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "http://qudt.org/vocab/unit/DEG_C"
    ]
    assert (imports_dir / "qudt-quantitykinds_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "http://qudt.org/vocab/quantitykind/Temperature"
    ]
    assert (imports_dir / "emmo-electrochemistry_terms.txt").read_text(encoding="utf-8").strip().splitlines() == [
        "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_123"
    ]
    assert (imports_dir / "emmo-core_terms.txt").read_text(encoding="utf-8") == ""


def test_build_actual_imports_report_accepts_small_semantic_annotation_module(tmp_path):
    config_dir = tmp_path / "config"
    imports_dir = tmp_path / "workbench" / "imports"
    config_dir.mkdir(parents=True)
    imports_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: dcterms",
                "    title: Dublin Core Terms",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (imports_dir / "dcterms_terms.txt").write_text("http://purl.org/dc/terms/title\n", encoding="utf-8", newline="\n")
    (imports_dir / "dcterms_import.owl").write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:owl="http://www.w3.org/2002/07/owl#">',
                '<owl:Ontology rdf:about="http://purl.obolibrary.org/obo/h2kg/imports/dcterms_import.owl"/>',
                '<owl:AnnotationProperty rdf:about="http://purl.org/dc/terms/title"/>',
                "</rdf:RDF>",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report = _build_actual_imports_report(config_dir, tmp_path / "workbench")
    item = report["imports"][0]
    assert item["status"] == "configured"
    assert report["summary"]["required_failed"] == 0


def test_build_actual_imports_report_marks_optional_unseeded_import_unused(tmp_path):
    config_dir = tmp_path / "config"
    imports_dir = tmp_path / "workbench" / "imports"
    config_dir.mkdir(parents=True)
    imports_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: vann",
                "    title: VANN",
                "    enabled: true",
                "    required: false",
                "    kind: ontology",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (imports_dir / "vann_terms.txt").write_text("", encoding="utf-8", newline="\n")
    (imports_dir / "vann_import.owl").write_text(
        "\n".join(
            [
                'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/vann_import.owl>)',
                'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)',
                "",
                'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/vann_import.owl>)',
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report = _build_actual_imports_report(config_dir, tmp_path / "workbench")
    item = report["imports"][0]
    assert item["status"] == "optional-unused-after-refresh"
    assert item["included_in_release"] is False


def test_build_ci_reproducibility_report_detects_complete_workflow_sequence(tmp_path):
    project_root = tmp_path / "ontology_release"
    workflow_dir = tmp_path / ".github" / "workflows"
    project_root.mkdir(parents=True)
    workflow_dir.mkdir(parents=True)
    workflow_text = "\n".join(
        [
            "name: Test",
            "jobs:",
            "  release:",
            "    steps:",
            "      - run: python -m aimworks_ontology_release.cli --project-root . odk --input input/current_ontology.jsonld --prepare-only",
            "      - run: docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v \"$PWD:/work\" -w /work/odk/src/ontology obolibrary/odkfull update_repo",
            "      - run: bash odk/src/ontology/run.sh make odkversion",
            "      - run: bash odk/src/ontology/run.sh make refresh-imports",
            "      - run: bash odk/src/ontology/run.sh make test",
            "      - run: bash odk/src/ontology/run.sh make prepare_release",
            "      - run: python -m aimworks_ontology_release.cli --project-root . odk --input input/current_ontology.jsonld --collect-only",
        ]
    )
    (workflow_dir / "ontology-release.yml").write_text(workflow_text, encoding="utf-8", newline="\n")
    (workflow_dir / "ontology-pages.yml").write_text(workflow_text, encoding="utf-8", newline="\n")

    report = _build_ci_reproducibility_report(project_root)

    assert report["status"] == "good"
    assert report["missing_workflows"] == []
    assert report["missing_steps"] == {}


def test_build_ci_reproducibility_report_reports_missing_steps(tmp_path):
    project_root = tmp_path / "ontology_release"
    workflow_dir = tmp_path / ".github" / "workflows"
    project_root.mkdir(parents=True)
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ontology-release.yml").write_text("name: release\n", encoding="utf-8", newline="\n")
    (workflow_dir / "ontology-pages.yml").write_text("name: pages\n", encoding="utf-8", newline="\n")

    report = _build_ci_reproducibility_report(project_root)

    assert report["status"] == "watch"
    assert "ontology-release.yml" in report["missing_steps"]
    assert "ontology-pages.yml" in report["missing_steps"]


def test_promotion_gates_use_ci_reproducibility_status():
    imports_report = {"summary": {"required_failed": 0}}
    parity = {"status": "aligned", "message": "ok", "artifact_incomplete": False, "iri_drift": False}
    ci = {"status": "good", "message": "workflow evidence present"}

    gates = _promotion_gates(imports_report, parity, ci)

    ci_gate = next(item for item in gates if item["label"] == "Reproducible CI build")
    assert ci_gate["status"] == "good"
    assert ci_gate["detail"] == "workflow evidence present"
