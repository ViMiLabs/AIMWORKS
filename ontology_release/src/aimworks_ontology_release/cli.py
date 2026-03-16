from __future__ import annotations

from pathlib import Path

import typer

from .profiles import available_profiles, run_multi_profile_pipeline, run_profile_pipeline
from .release import run_pipeline

app = typer.Typer(add_completion=False, help="AIMWORKS ontology release pipeline")


def _run_stage(
    stage: str,
    input: str | None,
    profile: str,
    draft_llm: bool = False,
    llm_config: Path | None = None,
    review_file: Path | None = None,
    apply_approved: Path | None = None,
    unit_evidence_dir: Path | None = None,
) -> None:
    if input:
        run_pipeline(
            input,
            stage=stage,
            draft_llm=draft_llm,
            llm_config_path=llm_config,
            review_file=review_file,
            apply_approved_file=apply_approved,
            unit_evidence_dir=unit_evidence_dir,
        )
        return
    run_profile_pipeline(
        profile_id=profile,
        stage=stage,
        draft_llm=draft_llm,
        llm_config_path=llm_config,
        review_file=review_file,
        apply_approved_file=apply_approved,
        unit_evidence_dir=unit_evidence_dir,
    )


@app.command()
def profiles() -> None:
    typer.echo("\n".join(available_profiles()))


@app.command()
def inspect(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
) -> None:
    _run_stage("inspect", input, profile)


@app.command()
def split(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
) -> None:
    _run_stage("split", input, profile)


@app.command()
def map(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
) -> None:
    _run_stage("map", input, profile)


@app.command()
def enrich(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("enrich", input, profile, unit_evidence_dir=unit_evidence_dir)


@app.command("units")
def units(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("units", input, profile, unit_evidence_dir=unit_evidence_dir)


@app.command()
def annotate(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    review_file: Path | None = typer.Option(None, "--review-file"),
    apply_approved: Path | None = typer.Option(None, "--apply-approved"),
) -> None:
    _run_stage(
        "annotate",
        input,
        profile,
        draft_llm=draft_llm,
        llm_config=llm_config,
        review_file=review_file,
        apply_approved=apply_approved,
    )


@app.command()
def validate(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("validate", input, profile, unit_evidence_dir=unit_evidence_dir)


@app.command()
def docs(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("docs", input, profile, unit_evidence_dir=unit_evidence_dir)


@app.command()
def fair(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("fair", input, profile, unit_evidence_dir=unit_evidence_dir)


@app.command()
def release(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    _run_stage("release", input, profile, draft_llm=draft_llm, llm_config=llm_config, unit_evidence_dir=unit_evidence_dir)


@app.command("docs-all")
def docs_all(
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    run_multi_profile_pipeline(stage="docs", draft_llm=draft_llm, llm_config_path=llm_config, unit_evidence_dir=unit_evidence_dir)


@app.command("release-all")
def release_all(
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    run_multi_profile_pipeline(stage="release", draft_llm=draft_llm, llm_config_path=llm_config, unit_evidence_dir=unit_evidence_dir)


@app.command()
def run(
    input: str | None = typer.Option(None, "--input"),
    profile: str = typer.Option("pemfc", "--profile"),
    build_docs: bool = typer.Option(True, "--build-docs/--no-build-docs"),
    build_release: bool = typer.Option(True, "--build-release/--no-build-release"),
    fair_check: bool = typer.Option(True, "--fair-check/--no-fair-check"),
    draft_llm: bool = typer.Option(False, "--draft-llm"),
    llm_config: Path | None = typer.Option(None, "--llm-config"),
    all_profiles: bool = typer.Option(False, "--all-profiles"),
    unit_evidence_dir: Path | None = typer.Option(None, "--unit-evidence-dir"),
) -> None:
    stage = "release" if build_release else "docs" if build_docs else "fair" if fair_check else "validate"
    if all_profiles and not input:
        run_multi_profile_pipeline(stage=stage, draft_llm=draft_llm, llm_config_path=llm_config, unit_evidence_dir=unit_evidence_dir)
        return
    _run_stage(stage, input, profile, draft_llm=draft_llm, llm_config=llm_config, unit_evidence_dir=unit_evidence_dir)


if __name__ == "__main__":
    app()
