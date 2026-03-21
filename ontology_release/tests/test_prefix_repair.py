from __future__ import annotations

import json

from aimworks_ontology_release.prefix_repair import repair_doc_prefixes
from aimworks_ontology_release.utils import canonical_qname


def test_canonical_qname_prefers_stable_prefixes() -> None:
    assert canonical_qname("https://w3id.org/h2kg/hydrogen-ontology#hasParameter", "ns1:hasParameter") == "h2kg:hasParameter"
    assert canonical_qname("http://purl.org/holy/ns#CatalystLayer", "ns6:CatalystLayer") == "holy:CatalystLayer"
    assert canonical_qname("http://qudt.org/schema/qudt/quantityKind", "ns4:quantityKind") == "qudt:quantityKind"


def test_repair_doc_prefixes_updates_reference_and_graph(tmp_path) -> None:
    docs_root = tmp_path / "pemfc"
    (docs_root / "data").mkdir(parents=True)
    (docs_root / "assets").mkdir(parents=True)

    (docs_root / "hydrogen-ontology.html").write_text(
        """<table><tbody>
<tr><td><code>ns1</code></td><td><a href="http://purl.org/holy/ns#"><code>http://purl.org/holy/ns#</code></a></td><td>4</td></tr>
<tr><td><code>ns2</code></td><td><a href="https://w3id.org/emmo/domain/electrochemistry#"><code>https://w3id.org/emmo/domain/electrochemistry#</code></a></td><td>4</td></tr>
</tbody></table>""",
        encoding="utf-8",
    )
    (docs_root / "assets" / "visuals.js").write_text(
        'const MAX_HISTORY = 40;\nconst qname = normalize(node.qname);\n"font-family": "Aptos, Gill Sans, Trebuchet MS, sans-serif",\n',
        encoding="utf-8",
    )
    (docs_root / "data" / "graph_explorer.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "iri": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
                        "qname": "ns1:hasParameter",
                        "search_text": "ns1:hasParameter",
                    }
                ],
                "links": [
                    {
                        "predicate": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
                        "value": "ns1:hasParameter",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = repair_doc_prefixes(docs_root)

    assert result["changed_count"] == 3
    html = (docs_root / "hydrogen-ontology.html").read_text(encoding="utf-8")
    assert "<code>holy</code>" in html
    assert "<code>electrochemistry</code>" in html
    graph = json.loads((docs_root / "data" / "graph_explorer.json").read_text(encoding="utf-8"))
    assert graph["nodes"][0]["qname"] == "h2kg:hasParameter"
    assert graph["links"][0]["value"] == "h2kg:hasParameter"
    visuals = (docs_root / "assets" / "visuals.js").read_text(encoding="utf-8")
    assert "const CANONICAL_PREFIXES = [" in visuals
    assert '"font-family": "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",' in visuals
