from __future__ import annotations

from pathlib import Path

import typer

from .release import run_pipeline

app = typer.Typer(add_completion=False, help="AIMWORKS ontology release pipeline")


@app.command()
def inspect(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="inspect")


@app.command()
def split(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="split")


@app.command()
def map(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="map")


@app.command()
def enrich(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="enrich")


@app.command()
def annotate(
    input: str = typer.Option("input/current_ontology.jsonld", "--input"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    review_file: Path | None = typer.Option(None, "--review-file"),
    apply_approved: Path | None = typer.Option(None, "--apply-approved"),
) -> None:
    run_pipeline(input, stage="annotate", draft_llm=draft_llm, llm_config_path=llm_config, review_file=review_file, apply_approved_file=apply_approved)


@app.command()
def validate(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="validate")


@app.command()
def docs(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="docs")


@app.command()
def fair(input: str = typer.Option("input/current_ontology.jsonld", "--input")) -> None:
    run_pipeline(input, stage="fair")


@app.command()
def release(
    input: str = typer.Option("input/current_ontology.jsonld", "--input"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
) -> None:
    run_pipeline(input, stage="release", draft_llm=draft_llm, llm_config_path=llm_config)


@app.command()
def run(
    input: str = typer.Option("input/current_ontology.jsonld", "--input"),
    build_docs: bool = typer.Option(True, "--build-docs/--no-build-docs"),
    build_release: bool = typer.Option(True, "--build-release/--no-build-release"),
    fair_check: bool = typer.Option(True, "--fair-check/--no-fair-check"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
) -> None:
    stage = "release" if build_release else "docs" if build_docs else "fair" if fair_check else "validate"
    run_pipeline(input, stage=stage, draft_llm=draft_llm, llm_config_path=llm_config)


if __name__ == "__main__":
    app()
