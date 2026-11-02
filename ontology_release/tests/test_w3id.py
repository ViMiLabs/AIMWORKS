from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.utils import default_release_profile
from aimworks_ontology_release.w3id import generate_w3id_artifacts


def test_w3id_keeps_established_routes_without_a_new_bridge_route(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    profile = default_release_profile()
    profile["project"]["contributors"] = [
        {
            "iri": "https://orcid.org/0009-0005-5173-202X",
            "label": "Marjan Kohandani",
            "github_handle": "Marjanknd",
            "affiliation_ids": ["a", "b", "c"],
            "contribution_order": 1,
        },
        {
            "iri": "https://orcid.org/0000-0002-5057-2993",
            "label": "Mohammad J. Eslamibidgoli",
            "github_handle": "meslamib3",
            "affiliation_ids": ["a", "b"],
            "contribution_order": 2,
        },
    ]
    (config_dir / "release_profile.yaml").write_text(
        json.dumps(profile),
        encoding="utf-8",
    )

    result = generate_w3id_artifacts(output_root / "w3id", config_dir)

    htaccess = (output_root / "w3id" / "h2kg" / ".htaccess").read_text(encoding="utf-8")
    readme = (output_root / "w3id" / "h2kg" / "README.md").read_text(encoding="utf-8")
    curls = (output_root / "w3id" / "curl_tests.sh").read_text(encoding="utf-8")
    publishing_notes = (output_root / "w3id" / "publishing_notes.md").read_text(encoding="utf-8")
    assert "hydrogen-ontology/bridge/tib" not in htaccess
    assert "h2kg-v2-external-bridge" not in htaccess
    assert "established `https://w3id.org/h2kg/` namespace" in readme
    assert "future pull request" not in readme.casefold()
    assert "does not require a new W3ID registration" in publishing_notes
    assert "Accept: text/turtle" in curls
    assert "hydrogen-ontology/bridge/tib" not in curls
    assert "external_bridge_ttl" not in result["rdf_targets"]
    assert "hydrogen-ontology/releases/([0-9]+\\.[0-9]+\\.[0-9]+)" in htaccess
    assert "AIMWORKS/v$1/ontology_release/output/ontology/h2kg-v2-taxonomy.ttl" in htaccess
    assert "^hydrogen-ontology$" in htaccess
    assert "h2kg-v2-taxonomy.ttl" in htaccess
    assert "application/ld\\+json" in htaccess
    assert "application/ld\\\\+json" not in htaccess
    assert "^hydrogen-ontology/core$" in htaccess
    assert "core_schema.ttl" in htaccess
    canonical_rule = next(
        line for line in htaccess.splitlines()
        if line.startswith("RewriteRule ^hydrogen-ontology$") and "ttl" in line
    )
    assert "h2kg-v2-taxonomy.ttl" in canonical_rule
    assert "releases/X.Y.Z" in readme
    assert "https://github.com/ViMiLabs/AIMWORKS/releases/tag/v2.3.1" in readme
    assert "AIMWORKS/v2.3.1/ontology_release/output/ontology/h2kg-v2-taxonomy.ttl" in readme
    assert "(`@Marjanknd`)" in readme
    assert "(`@meslamib3`)" in readme
    assert "pages/explore.html?view=taxonomy" not in readme
