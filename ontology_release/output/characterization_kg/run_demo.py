from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyshacl import validate
from rdflib import Dataset, Graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the H2KG characterization knowledge-graph demonstration")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--query", default="q1_tem_specimen_preparation")
    args = parser.parse_args()
    root = Path(args.root)
    dataset = Dataset()
    dataset.parse(root / "characterization_knowledge_graph.trig", format="trig")
    query = (root / "queries" / f"{args.query}.rq").read_text(encoding="utf-8")
    result = dataset.query(query)
    print(json.dumps([dict(zip([str(v) for v in result.vars], [str(x) if x is not None else "" for x in row])) for row in result], indent=2))
    flat = Graph().parse(root / "characterization_knowledge_graph.ttl", format="turtle")
    shapes = Graph().parse(root / "characterization_shapes.ttl", format="turtle")
    conforms, _, report = validate(flat, shacl_graph=shapes, inference="rdfs")
    print(f"SHACL conforms: {conforms}")
    if not conforms:
        print(report)


if __name__ == "__main__":
    main()
