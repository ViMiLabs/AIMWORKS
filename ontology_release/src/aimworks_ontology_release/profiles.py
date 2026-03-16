from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from .release import run_pipeline
from .utils import copy_file, copy_tree, ensure_dir, load_configs, load_yaml, write_json, write_text


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _profiles_config(root: Path) -> dict[str, Any]:
    payload = load_yaml(root / "config" / "ontology_profiles.yaml")
    if not payload.get("profiles"):
        raise ValueError("config/ontology_profiles.yaml must define at least one profile under `profiles`.")
    return payload


def _resolve_profile_input(base_root: Path, raw_path: str) -> Path:
    candidate = (base_root / raw_path).resolve()
    if candidate.exists():
        return candidate
    # Test and local fallback: if the relative path points outside the package, fall back to `input/<name>`.
    fallback = (base_root / "input" / Path(raw_path).name).resolve()
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Profile input ontology not found: {raw_path}")


def _safe_remove_tree(path: Path) -> None:
    if path.exists():
        try:
            shutil.rmtree(path)
        except OSError:
            shutil.rmtree(path, ignore_errors=True)


def _prepare_profile_runtime(base_root: Path, profile_id: str, profile_cfg: dict[str, Any], profiles_cfg: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    runtime_root = base_root / "output" / "profiles" / profile_id / "workspace"
    _safe_remove_tree(runtime_root)
    ensure_dir(runtime_root)

    for dirname in ["config", "templates", "shapes"]:
        copy_tree(base_root / dirname, runtime_root / dirname)
    for filename in ["CITATION.cff", ".zenodo.json", ".nojekyll", "README.md"]:
        copy_file(base_root / filename, runtime_root / filename)

    ensure_dir(runtime_root / "input")
    ensure_dir(runtime_root / "output")
    ensure_dir(runtime_root / "ontology")
    ensure_dir(runtime_root / "cache" / "sources")

    source_input = _resolve_profile_input(base_root, str(profile_cfg["input_path"]))
    copy_file(source_input, runtime_root / "input" / "current_ontology.jsonld")

    base_configs = load_configs(base_root)
    runtime_release = deepcopy(base_configs["release_profile"])
    site_cfg = profiles_cfg.get("site", {})
    runtime_release["project"]["title"] = site_cfg.get("title", runtime_release["project"]["title"])
    runtime_release["project"]["subtitle"] = profile_cfg.get("project_overrides", {}).get("subtitle", runtime_release["project"]["subtitle"])
    runtime_release["project"]["short_title"] = profile_cfg.get("project_overrides", {}).get("short_title", runtime_release["project"].get("short_title", runtime_release["project"]["title"]))
    runtime_release["project"]["profile_id"] = profile_id
    runtime_release["project"]["profile_label"] = profile_cfg["label"]

    doc_cfg = runtime_release.setdefault("documentation", {})
    doc_cfg["site_title"] = site_cfg.get("title", doc_cfg.get("site_title", runtime_release["project"]["title"]))
    doc_cfg["profile_id"] = profile_id
    doc_cfg["profile_label"] = profile_cfg["label"]
    doc_cfg["profile_slug"] = profile_cfg["slug"]
    doc_cfg["profile_heading"] = profile_cfg.get("profile_heading", f"{profile_cfg['label']} Ontology Profile")
    doc_cfg["landing_intro"] = profile_cfg.get("documentation_overrides", {}).get("landing_intro", doc_cfg.get("landing_intro", ""))
    doc_cfg["site_tagline"] = profile_cfg.get("documentation_overrides", {}).get("site_tagline", doc_cfg.get("site_tagline", ""))

    doc_cfg = _deep_merge(doc_cfg, profile_cfg.get("documentation_overrides", {}))
    pages_base = str(site_cfg.get("pages_base_path", "/AIMWORKS")).rstrip("/")
    switch_rows = []
    for other_id in profiles_cfg.get("build_order", list(profiles_cfg["profiles"].keys())):
        other_cfg = profiles_cfg["profiles"][other_id]
        switch_rows.append(
            {
                "id": other_id,
                "label": other_cfg["label"],
                "href": f"{pages_base}/{other_cfg['slug']}/index.html",
                "active": other_id == profile_id,
            }
        )
    doc_cfg["profile_switch"] = switch_rows
    doc_cfg.setdefault("resources", {})
    default_pages_url = doc_cfg["resources"].get("pages_url", f"https://vimilabs.github.io{pages_base}/")
    doc_cfg["resources"]["pages_url"] = f"{str(default_pages_url).rstrip('/')}/{profile_cfg['slug']}/"
    runtime_release["documentation"] = doc_cfg

    runtime_namespace = deepcopy(base_configs["namespace_policy_raw"])
    namespace_overrides = profile_cfg.get("namespace_overrides", {})
    if namespace_overrides:
        active_name = runtime_namespace["active_profile"]
        runtime_namespace["profiles"][active_name] = _deep_merge(runtime_namespace["profiles"][active_name], namespace_overrides)

    write_text(runtime_root / "config" / "release_profile.yaml", _yaml_dump(runtime_release))
    write_text(runtime_root / "config" / "namespace_policy.yaml", _yaml_dump(runtime_namespace))

    return runtime_root, runtime_release


def _yaml_dump(payload: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def _profile_output_root(base_root: Path, profile_id: str) -> Path:
    return ensure_dir(base_root / "output" / "profiles" / profile_id)


def _copy_runtime_results_to_profile(base_root: Path, profile_id: str, runtime_root: Path) -> None:
    target = _profile_output_root(base_root, profile_id)
    _safe_remove_tree(target / "output")
    _safe_remove_tree(target / "ontology")
    copy_tree(runtime_root / "output", target / "output")
    copy_tree(runtime_root / "ontology", target / "ontology")
    write_json(target / "profile.json", {"profile_id": profile_id})


def _assemble_multi_publication(base_root: Path, built_profiles: list[dict[str, Any]], site_cfg: dict[str, Any]) -> None:
    publication_root = ensure_dir(base_root / "output" / "publication")
    docs_root = ensure_dir(base_root / "output" / "docs")
    _safe_remove_tree(publication_root)
    _safe_remove_tree(docs_root)
    ensure_dir(publication_root)
    ensure_dir(docs_root)

    profile_cards = []
    for item in built_profiles:
        profile_id = item["profile_id"]
        slug = item["slug"]
        label = item["label"]
        runtime_root = item["runtime_root"]
        copy_tree(runtime_root / "output" / "publication", publication_root / slug)
        copy_tree(runtime_root / "output" / "docs", docs_root / slug)
        profile_cards.append(
            {
                "id": profile_id,
                "slug": slug,
                "label": label,
                "href": f"./{slug}/index.html",
                "reference": f"./{slug}/hydrogen-ontology.html",
                "queries": f"./{slug}/pages/queries.html",
            }
        )

    landing_title = site_cfg.get("title", "H2KG — Ontology for Hydrogen Electrochemical Systems")
    landing_subtitle = site_cfg.get("subtitle", "Multi-profile ontology publication")
    landing_html = _landing_html(landing_title, landing_subtitle, profile_cards)
    write_text(publication_root / "index.html", landing_html)
    write_text(docs_root / "index.html", landing_html)
    write_json(publication_root / "profiles.json", profile_cards)
    write_text(publication_root / ".nojekyll", "")


def _assemble_multi_release_bundle(base_root: Path, built_profiles: list[dict[str, Any]]) -> None:
    release_root = base_root / "output" / "release_bundle"
    _safe_remove_tree(release_root)
    ensure_dir(release_root)
    for item in built_profiles:
        runtime_root = item["runtime_root"]
        slug = item["slug"]
        copy_tree(runtime_root / "output" / "release_bundle", release_root / slug)
    if (base_root / "output" / "publication").exists():
        copy_tree(base_root / "output" / "publication", release_root / "publication")
    write_json(
        release_root / "profiles.json",
        [{"profile_id": item["profile_id"], "slug": item["slug"], "label": item["label"]} for item in built_profiles],
    )


def _landing_html(title: str, subtitle: str, cards: list[dict[str, str]]) -> str:
    card_html = []
    for card in cards:
        card_html.append(
            f"""
      <article class="card">
        <h2>{card['label']} Profile</h2>
        <p>Browse profile-specific ontology docs, release outputs, alignments, validation, and query tooling.</p>
        <div class="links">
          <a href="{card['href']}">Open profile home</a>
          <a href="{card['reference']}">Open reference</a>
          <a href="{card['queries']}">Open queries</a>
        </div>
      </article>
"""
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --ink: #10242d;
      --muted: #4d6370;
      --line: rgba(16,36,45,0.14);
      --accent: #0d7f83;
      --paper: #ffffff;
      --shadow: 0 16px 44px rgba(16,36,45,0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Aptos", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(13,127,131,0.2), transparent 32%),
        linear-gradient(180deg, #edf8f7 0%, #fbf6ef 100%);
    }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 2rem 1rem 3rem; }}
    h1, h2 {{ font-family: "Iowan Old Style", Georgia, serif; letter-spacing: -0.02em; }}
    h1 {{ margin: 0 0 0.5rem; font-size: clamp(1.95rem, 4.3vw, 2.8rem); line-height: 1.08; max-width: 16ch; text-wrap: balance; }}
    p {{ color: var(--muted); line-height: 1.55; }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin-top: 1.3rem; }}
    .card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 1.25rem; padding: 1.1rem; box-shadow: var(--shadow); }}
    .links {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: 0.8rem; }}
    a {{
      text-decoration: none;
      color: white;
      background: linear-gradient(135deg, #10242d, var(--accent));
      border-radius: 999px;
      padding: 0.45rem 0.82rem;
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="grid">
{''.join(card_html)}
    </div>
  </main>
</body>
</html>
"""


def run_profile_pipeline(
    profile_id: str,
    stage: str = "release",
    root: Path | None = None,
    draft_llm: bool = False,
    llm_config_path: Path | None = None,
    review_file: Path | None = None,
    apply_approved_file: Path | None = None,
    input_override: str | None = None,
    unit_evidence_dir: Path | None = None,
) -> dict[str, Any]:
    base_root = root or Path(__file__).resolve().parents[2]
    profiles_cfg = _profiles_config(base_root)
    if profile_id not in profiles_cfg["profiles"]:
        available = ", ".join(sorted(profiles_cfg["profiles"].keys()))
        raise ValueError(f"Unknown profile `{profile_id}`. Available profiles: {available}")

    profile_cfg = deepcopy(profiles_cfg["profiles"][profile_id])
    if input_override:
        profile_cfg["input_path"] = input_override

    runtime_root, runtime_release = _prepare_profile_runtime(base_root, profile_id, profile_cfg, profiles_cfg)
    resolved_unit_evidence_dir = None
    if unit_evidence_dir is not None:
        resolved_unit_evidence_dir = unit_evidence_dir if unit_evidence_dir.is_absolute() else (base_root / unit_evidence_dir).resolve()
    result = run_pipeline(
        "input/current_ontology.jsonld",
        root=runtime_root,
        stage=stage,
        draft_llm=draft_llm,
        llm_config_path=llm_config_path,
        review_file=review_file,
        apply_approved_file=apply_approved_file,
        unit_evidence_dir=resolved_unit_evidence_dir,
    )
    _copy_runtime_results_to_profile(base_root, profile_id, runtime_root)

    if stage in {"docs", "release", "fair"}:
        _assemble_multi_publication(
            base_root,
            [
                {
                    "profile_id": profile_id,
                    "slug": profile_cfg["slug"],
                    "label": profile_cfg["label"],
                    "runtime_root": runtime_root,
                }
            ],
            profiles_cfg.get("site", {}),
        )
    if stage == "release":
        _assemble_multi_release_bundle(
            base_root,
            [
                {
                    "profile_id": profile_id,
                    "slug": profile_cfg["slug"],
                    "label": profile_cfg["label"],
                    "runtime_root": runtime_root,
                }
            ],
        )

    result["profile_id"] = profile_id
    result["profile_label"] = profile_cfg["label"]
    result["profile_slug"] = profile_cfg["slug"]
    result["profile_release_title"] = runtime_release["project"]["title"]
    return result


def run_multi_profile_pipeline(
    stage: str = "release",
    root: Path | None = None,
    profile_ids: list[str] | None = None,
    draft_llm: bool = False,
    llm_config_path: Path | None = None,
    unit_evidence_dir: Path | None = None,
) -> dict[str, Any]:
    base_root = root or Path(__file__).resolve().parents[2]
    profiles_cfg = _profiles_config(base_root)
    requested = profile_ids or list(profiles_cfg.get("build_order") or profiles_cfg["profiles"].keys())
    built_rows: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {"profiles": {}}
    resolved_unit_evidence_dir = None
    if unit_evidence_dir is not None:
        resolved_unit_evidence_dir = unit_evidence_dir if unit_evidence_dir.is_absolute() else (base_root / unit_evidence_dir).resolve()

    for profile_id in requested:
        if profile_id not in profiles_cfg["profiles"]:
            available = ", ".join(sorted(profiles_cfg["profiles"].keys()))
            raise ValueError(f"Unknown profile `{profile_id}`. Available profiles: {available}")
        profile_cfg = profiles_cfg["profiles"][profile_id]
        runtime_root, _ = _prepare_profile_runtime(base_root, profile_id, profile_cfg, profiles_cfg)
        result = run_pipeline(
            "input/current_ontology.jsonld",
            root=runtime_root,
            stage=stage,
            draft_llm=draft_llm,
            llm_config_path=llm_config_path,
            unit_evidence_dir=resolved_unit_evidence_dir,
        )
        _copy_runtime_results_to_profile(base_root, profile_id, runtime_root)
        outputs["profiles"][profile_id] = result
        built_rows.append(
            {
                "profile_id": profile_id,
                "slug": profile_cfg["slug"],
                "label": profile_cfg["label"],
                "runtime_root": runtime_root,
            }
        )

    if stage in {"docs", "release", "fair"}:
        _assemble_multi_publication(base_root, built_rows, profiles_cfg.get("site", {}))
    if stage == "release":
        _assemble_multi_release_bundle(base_root, built_rows)
    return outputs


def available_profiles(root: Path | None = None) -> list[str]:
    base_root = root or Path(__file__).resolve().parents[2]
    cfg = _profiles_config(base_root)
    return list(cfg["profiles"].keys())
