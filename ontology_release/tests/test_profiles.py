from __future__ import annotations

from aimworks_ontology_release.profiles import available_profiles, run_multi_profile_pipeline, run_profile_pipeline


def test_profile_registry_available(temp_project):
    names = available_profiles(temp_project)
    assert "pemfc" in names
    assert "pemwe" in names


def test_multi_profile_docs_build(temp_project):
    run_multi_profile_pipeline(stage="docs", root=temp_project)
    assert (temp_project / "output" / "publication" / "index.html").exists()
    assert (temp_project / "output" / "publication" / "pemfc" / "pages" / "queries.html").exists()
    assert (temp_project / "output" / "publication" / "pemwe" / "pages" / "queries.html").exists()
    assert (temp_project / "output" / "profiles" / "pemfc" / "output" / "reports" / "inspection_report.json").exists()
    assert (temp_project / "output" / "profiles" / "pemwe" / "output" / "reports" / "inspection_report.json").exists()


def test_single_profile_release_build(temp_project):
    result = run_profile_pipeline(profile_id="pemwe", stage="release", root=temp_project)
    assert result["profile_id"] == "pemwe"
    assert (temp_project / "output" / "profiles" / "pemwe" / "output" / "release_bundle" / "manifest.json").exists()
    assert (temp_project / "output" / "publication" / "pemwe" / "index.html").exists()
    assert (temp_project / "output" / "release_bundle" / "pemwe" / "manifest.json").exists()
