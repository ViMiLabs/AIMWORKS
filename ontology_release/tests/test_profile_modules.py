from __future__ import annotations

from aimworks_ontology_release.profile_modules import build_profile_modules
from aimworks_ontology_release.utils import H2KG_APPLIES_TO_PROFILE


def test_profile_modules_emit_profile_ontologies(mini_ontology_file, output_dir):
    (output_dir / "ontology").mkdir()
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    result = build_profile_modules(mini_ontology_file, output_dir / "ontology")
    assert result["core_ontology_iri"] == "https://w3id.org/h2kg/hydrogen-ontology"
    assert result["pemfc_ontology_iri"] == "https://w3id.org/h2kg/pemfc/hydrogen-ontology"
    assert result["pemwe_ontology_iri"] == "https://w3id.org/h2kg/pemwe/hydrogen-ontology"
    assert (output_dir / "ontology" / "core_schema.ttl").exists()
    assert (output_dir / "ontology" / "pemfc_schema.ttl").exists()
    assert (output_dir / "ontology" / "pemwe_schema.ttl").exists()


def test_profile_modules_add_profile_annotation(mini_ontology_file, output_dir):
    (output_dir / "ontology").mkdir()
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    build_profile_modules(mini_ontology_file, output_dir / "ontology")
    pemfc_jsonld = (output_dir / "ontology" / "pemfc_schema.jsonld").read_text(encoding="utf-8")
    assert H2KG_APPLIES_TO_PROFILE in pemfc_jsonld
