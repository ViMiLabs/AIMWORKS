from __future__ import annotations

from aimworks_ontology_release.index import build_source_index


def test_source_index_reads_local_hdo_cache(tmp_path):
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache" / "sources"
    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        """
sources:
  - id: hdo
    title: Helmholtz Digitisation Ontology
    enabled: true
    priority: 78
    required: true
    kind: ontology
    local_cache: cache/sources/hdo.owl
    remote_url: https://purls.helmholtz-metadaten.de/hob/hdo.owl
""",
        encoding="utf-8",
    )
    (cache_dir / "hdo.owl").write_text(
        """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Class rdf:about="https://purls.helmholtz-metadaten.de/hob/HDO_00000043">
    <rdfs:label>persistent identifier</rdfs:label>
    <rdfs:comment>A persistent identifier concept from a local HDO cache fixture.</rdfs:comment>
  </owl:Class>
</rdf:RDF>
""",
        encoding="utf-8",
    )
    terms = build_source_index(config_dir)
    assert any(term["source"] == "hdo" and term["label"] == "persistent identifier" for term in terms)
