from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from .extract import collect_examples, extract_local_terms
from .inspect import find_ontology_node
from .io import load_graph
from .normalize import humanize_identifier
from .publication import reference_iri_rows
from .utils import QUDT, copy_file, ensure_dir, load_yaml, local_name, normalize_space, read_csv, read_json, write_json, write_text


SITE_CSS = """
:root {
  --slate-950: #0e1a21;
  --slate-900: #122730;
  --slate-800: #1d3943;
  --teal-700: #1f7a7a;
  --teal-500: #4db4aa;
  --copper-500: #ca6d2c;
  --copper-300: #e5b07a;
  --mist-50: #f4fbfb;
  --sand-50: #fbf6ef;
  --paper: rgba(255, 255, 255, 0.9);
  --panel: rgba(255, 255, 255, 0.82);
  --muted: #56636c;
  --line: rgba(18, 39, 48, 0.12);
  --line-strong: rgba(18, 39, 48, 0.24);
  --shadow: 0 24px 70px rgba(14, 26, 33, 0.13);
  --shadow-soft: 0 14px 38px rgba(14, 26, 33, 0.09);
  --radius: 24px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 0% 0%, rgba(77, 180, 170, 0.32), transparent 38%),
    radial-gradient(circle at 100% 12%, rgba(202, 109, 44, 0.18), transparent 28%),
    linear-gradient(180deg, rgba(18, 39, 48, 0.05) 0%, transparent 12%),
    linear-gradient(180deg, #edf8f7 0%, #f8fbfa 48%, #f8f2e8 100%);
  color: var(--slate-950);
  font-family: "Aptos", "Gill Sans", "Trebuchet MS", sans-serif;
  line-height: 1.55;
}
body::before,
body::after {
  content: "";
  position: fixed;
  width: 18rem;
  height: 18rem;
  border-radius: 999px;
  filter: blur(30px);
  opacity: 0.4;
  z-index: -1;
}
body::before {
  top: 2rem;
  right: 4vw;
  background: radial-gradient(circle, rgba(77, 180, 170, 0.55), transparent 65%);
}
body::after {
  bottom: 4rem;
  left: 3vw;
  background: radial-gradient(circle, rgba(202, 109, 44, 0.36), transparent 62%);
}
a {
  color: var(--teal-700);
  text-decoration-thickness: 1px;
  text-underline-offset: 0.15em;
}
a:hover { color: var(--slate-900); }
code {
  font-family: "Cascadia Code", "IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace;
  font-size: 0.92em;
  background: rgba(18, 39, 48, 0.06);
  border-radius: 0.45rem;
  padding: 0.08rem 0.35rem;
}
pre {
  overflow: auto;
  background: linear-gradient(180deg, #10232c, #15323c);
  color: #eef8f7;
  border-radius: 1.15rem;
  padding: 1rem 1.1rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
pre code {
  background: none;
  padding: 0;
  color: inherit;
}
.site-shell {
  position: relative;
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 1rem 4rem;
}
.hero {
  position: relative;
  overflow: hidden;
  padding: 1.45rem 0 0.35rem;
}
.hero__band {
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 0.58rem;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--teal-700), var(--teal-500) 52%, var(--copper-500));
  box-shadow: 0 10px 30px rgba(31, 122, 122, 0.22);
}
.hero__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.9fr);
  gap: 1rem;
  padding-top: 1.65rem;
  align-items: stretch;
}
.hero__content,
.hero__panel {
  border-radius: 2rem;
  border: 1px solid rgba(18, 39, 48, 0.08);
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}
.hero__content {
  position: relative;
  overflow: hidden;
  padding: 1.5rem 1.55rem 1.35rem;
  background:
    radial-gradient(circle at 92% 12%, rgba(255, 255, 255, 0.38), transparent 22%),
    linear-gradient(140deg, rgba(255, 255, 255, 0.93), rgba(255, 255, 255, 0.76));
}
.hero__content::after {
  content: "";
  position: absolute;
  top: -4rem;
  right: -3rem;
  width: 16rem;
  height: 16rem;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(31, 122, 122, 0.14), rgba(31, 122, 122, 0) 68%);
}
.hero__panel {
  padding: 1.3rem 1.2rem;
  background:
    radial-gradient(circle at top right, rgba(229, 176, 122, 0.16), transparent 30%),
    linear-gradient(180deg, rgba(18, 39, 48, 0.96), rgba(18, 39, 48, 0.86));
  color: #ecf7f5;
}
.hero__label {
  margin: 0 0 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.76rem;
  font-weight: 700;
  color: rgba(236, 247, 245, 0.7);
}
.hero__note {
  margin: 0 0 1rem;
  color: rgba(236, 247, 245, 0.82);
}
.hero-fact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.hero-fact {
  padding: 0.85rem 0.9rem;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
}
.hero-fact span {
  display: block;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: rgba(236, 247, 245, 0.58);
}
.hero-fact strong {
  display: block;
  margin-top: 0.4rem;
  font-size: 1.08rem;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.eyebrow {
  margin: 0 0 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--copper-500);
  font-size: 0.78rem;
  font-weight: 700;
}
h1,
h2,
h3 {
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
  line-height: 1.05;
  letter-spacing: -0.02em;
}
h1 {
  font-size: clamp(2.2rem, 4.8vw, 3.7rem);
  margin: 0.15rem 0 0.8rem;
  max-width: 16ch;
  text-wrap: balance;
}
h2 {
  margin-top: 0;
  font-size: clamp(1.6rem, 2.4vw, 2.2rem);
}
h3 {
  font-size: 1.12rem;
  margin: 0 0 0.55rem;
}
.lede {
  max-width: 62ch;
  color: var(--muted);
  font-size: 1.06rem;
  margin: 0 0 1rem;
}
.meta-row {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin: 0 0 1rem;
}
.meta-row span,
.metric-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  border: 1px solid rgba(18, 39, 48, 0.09);
  background: rgba(255, 255, 255, 0.78);
  padding: 0.34rem 0.72rem;
  font-size: 0.84rem;
  color: var(--muted);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}
.action-row {
  display: flex;
  gap: 0.7rem;
  flex-wrap: wrap;
}
.action-row a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.75rem;
  text-decoration: none;
  color: var(--slate-950);
  border: 1px solid rgba(18, 39, 48, 0.12);
  padding: 0.55rem 0.95rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.action-row a.primary {
  background: linear-gradient(135deg, var(--slate-900), var(--teal-700) 58%, var(--copper-500));
  border-color: transparent;
  color: #ffffff;
}
.action-row a:hover {
  transform: translateY(-1px);
  border-color: rgba(31, 122, 122, 0.3);
  box-shadow: var(--shadow-soft);
}
.nav-shell {
  position: sticky;
  top: 0.45rem;
  z-index: 20;
  margin: 1.05rem 0 1.45rem;
}
.nav {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.72rem;
  border-radius: 999px;
  border: 1px solid rgba(18, 39, 48, 0.08);
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 18px 40px rgba(14, 26, 33, 0.08);
  backdrop-filter: blur(14px);
}
.nav a {
  text-decoration: none;
  color: var(--slate-900);
  padding: 0.48rem 0.88rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 0.92rem;
}
.nav a:hover {
  border-color: rgba(31, 122, 122, 0.22);
  background: rgba(18, 39, 48, 0.06);
}
.content { display: grid; gap: 1rem; }
.grid { display: grid; gap: 1rem; }
.grid.two { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.grid.three { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.grid.four { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
.landing-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.85fr);
  gap: 1rem;
}
.home-showcase {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.45fr);
  gap: 1rem;
  padding: 1.25rem;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.12), transparent 28%),
    radial-gradient(circle at bottom right, rgba(202, 109, 44, 0.14), transparent 26%),
    linear-gradient(145deg, rgba(14, 26, 33, 0.98), rgba(21, 56, 66, 0.94) 60%, rgba(31, 122, 122, 0.84));
  color: #f7fcfb;
  box-shadow: var(--shadow);
}
.home-showcase::after {
  display: none;
}
.home-showcase__copy {
  display: grid;
  align-content: center;
  gap: 0.95rem;
}
.home-showcase__copy p,
.home-showcase__copy li,
.home-showcase__copy a,
.home-showcase__copy h2 {
  color: inherit;
}
.home-showcase__copy .section-kicker {
  color: #fdd9b4;
}
.home-showcase__copy .lede {
  color: rgba(247, 252, 251, 0.8);
  max-width: 52ch;
}
.home-showcase__frame {
  position: relative;
  margin: 0;
  padding: 0.95rem;
  border-radius: 1.7rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.06));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.home-showcase__frame::before {
  content: "";
  position: absolute;
  inset: auto 12% -18% 12%;
  height: 28%;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(77, 180, 170, 0.2), transparent 72%);
  filter: blur(24px);
}
.home-showcase__image {
  position: relative;
  display: block;
  width: 100%;
  height: auto;
  border-radius: 1.15rem;
  background: #ffffff;
  box-shadow: 0 26px 54px rgba(7, 17, 22, 0.28);
}
.home-showcase__caption {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  margin-top: 0.8rem;
  font-size: 0.88rem;
  color: rgba(247, 252, 251, 0.76);
}
.home-showcase__metrics {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.home-showcase__metrics .metric-pill {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(247, 252, 251, 0.86);
}
.support-card {
  background:
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.1), transparent 28%),
    linear-gradient(145deg, rgba(18, 39, 48, 0.98), rgba(31, 122, 122, 0.92) 58%, rgba(202, 109, 44, 0.8));
  color: #f7fcfb;
}
.support-card p,
.support-card a,
.support-card h2 {
  color: inherit;
}
.support-card .section-kicker {
  color: #fdd9b4;
}
.support-card__brand {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  margin-bottom: 0.9rem;
  padding: 0.8rem 0.95rem;
  border-radius: 1.2rem;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.support-card__brand img {
  width: min(100%, 220px);
  height: auto;
  display: block;
}
.support-card__links {
  display: flex;
  gap: 0.7rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}
.support-card__links a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.6rem;
  padding: 0.5rem 0.92rem;
  text-decoration: none;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}
.support-card__links a:hover {
  background: rgba(255, 255, 255, 0.14);
}
.card {
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.86));
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.2rem 1.25rem;
  box-shadow: var(--shadow-soft);
}
.card::after {
  content: "";
  position: absolute;
  right: 1.15rem;
  bottom: 0.9rem;
  width: 3.25rem;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(18, 39, 48, 0.18));
}
.card--feature {
  background:
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.14), transparent 28%),
    linear-gradient(145deg, rgba(18, 39, 48, 0.96), rgba(31, 122, 122, 0.92) 60%, rgba(202, 109, 44, 0.82));
  color: #f7fcfb;
  box-shadow: var(--shadow);
}
.card--feature .lede,
.card--feature p,
.card--feature li,
.card--feature a,
.card--feature h2,
.card--feature h3 {
  color: inherit;
}
.card--feature .section-kicker { color: #fdd9b4; }
.card--accent {
  background: linear-gradient(180deg, rgba(255, 247, 236, 0.98), rgba(255, 255, 255, 0.92));
}
.card--quiet {
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.9), rgba(255, 255, 255, 0.86));
}
.section-kicker {
  margin: 0 0 0.45rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--teal-700);
}
.score {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 5.4rem;
  height: 5.4rem;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--slate-900), var(--teal-700) 55%, var(--copper-500));
  color: #ffffff;
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 0.85rem;
  box-shadow: 0 14px 32px rgba(31, 122, 122, 0.2);
}
.simple-list {
  margin: 0.1rem 0 0;
  padding-left: 1.15rem;
}
.simple-list li { margin-bottom: 0.46rem; }
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.chip-row a,
.chip-row span {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  text-decoration: none;
  color: var(--slate-900);
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.94), rgba(255, 247, 236, 0.94));
  border-radius: 999px;
  border: 1px solid rgba(18, 39, 48, 0.1);
  padding: 0.38rem 0.76rem;
  font-size: 0.86rem;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.32rem 0.7rem;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
  border: 1px solid transparent;
}
.status-good {
  color: #166534;
  background: rgba(220, 252, 231, 0.78);
  border-color: rgba(22, 101, 52, 0.15);
}
.status-watch {
  color: #9a5a08;
  background: rgba(254, 243, 199, 0.88);
  border-color: rgba(154, 90, 8, 0.16);
}
.status-action {
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.82);
  border-color: rgba(185, 28, 28, 0.16);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.8rem;
}
.kpi {
  border: 1px solid var(--line);
  border-radius: 1.2rem;
  padding: 1rem;
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.86), rgba(255, 255, 255, 0.92));
}
.kpi__value {
  display: block;
  font-size: 1.75rem;
  font-weight: 700;
  margin-bottom: 0.2rem;
}
.kpi__label {
  display: block;
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}
.kpi__detail {
  margin: 0.25rem 0 0;
  font-size: 0.92rem;
  color: var(--muted);
}
.mini-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.8rem;
}
.mini-stat {
  border-radius: 1rem;
  padding: 0.9rem 0.95rem;
  border: 1px solid rgba(18, 39, 48, 0.08);
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.86), rgba(255, 247, 236, 0.74));
}
.card--feature .mini-stat {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
}
.mini-stat span {
  display: block;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--muted);
}
.card--feature .mini-stat span { color: rgba(247, 252, 251, 0.6); }
.mini-stat strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 1.02rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.feature-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.85rem;
}
.feature-item {
  display: block;
  height: 100%;
  border: 1px solid var(--line);
  border-radius: 1.2rem;
  padding: 1rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(244, 251, 251, 0.78));
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  color: inherit;
  text-decoration: none;
}
.feature-item:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-soft);
}
.feature-item h3 a {
  color: inherit;
  text-decoration: none;
}
.feature-item p { margin-bottom: 0; }
.timeline { display: grid; gap: 0.8rem; }
.timeline__item {
  border-left: 3px solid var(--teal-700);
  padding-left: 1rem;
}
.query-card,
.diagram-card,
.check-card {
  border: 1px solid var(--line);
  border-radius: 1.4rem;
  padding: 1rem 1.1rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(244, 251, 251, 0.8));
  box-shadow: var(--shadow-soft);
}
.query-meta {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin-bottom: 0.7rem;
}
.copy-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.55rem;
}
.copy-button {
  border: 1px solid rgba(18, 39, 48, 0.12);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 251, 251, 0.88));
  padding: 0.5rem 0.92rem;
  cursor: pointer;
}
.copy-button:hover {
  border-color: rgba(31, 122, 122, 0.24);
  color: var(--teal-700);
}
.query-source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.7rem;
  margin: 0.8rem 0 0.95rem;
}
.source-option {
  display: grid;
  gap: 0.35rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.82);
  padding: 0.72rem 0.82rem;
}
.source-option input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--teal-700);
}
.source-option strong {
  display: block;
  font-size: 0.94rem;
}
.source-option code {
  font-size: 0.79rem;
  overflow-wrap: anywhere;
}
.query-editor {
  width: 100%;
  min-height: 17rem;
  border: 1px solid rgba(18, 39, 48, 0.14);
  border-radius: 1.1rem;
  padding: 0.95rem 1rem;
  font-family: "Cascadia Code", "IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace;
  font-size: 0.9rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 251, 251, 0.86));
  color: var(--slate-950);
  resize: vertical;
}
.query-editor:focus {
  outline: none;
  border-color: rgba(31, 122, 122, 0.36);
  box-shadow: 0 0 0 4px rgba(31, 122, 122, 0.12);
}
.query-toolbar {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 0.8rem;
}
.query-hint {
  font-size: 0.9rem;
  color: var(--muted);
  margin-top: 0.8rem;
}
.result-panel { margin-top: 0.55rem; }
.is-hidden { display: none; }
.result-tab.is-active {
  border-color: rgba(31, 122, 122, 0.4);
  background: linear-gradient(180deg, rgba(31, 122, 122, 0.14), rgba(202, 109, 44, 0.14));
  color: var(--slate-900);
}
.svg-frame {
  border: 1px solid var(--line);
  border-radius: 1.15rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(244, 251, 251, 0.82));
  padding: 0.6rem;
  overflow-x: auto;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}
.check-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
}
.callout {
  border-left: 4px solid var(--copper-500);
  padding: 1rem 1.05rem;
  background: linear-gradient(90deg, rgba(255, 243, 227, 0.96), rgba(255, 255, 255, 0.88));
  border-radius: 1rem;
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: end;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.filter-input {
  width: min(320px, 100%);
  padding: 0.76rem 1rem;
  border: 1px solid rgba(18, 39, 48, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}
.filter-input:focus {
  outline: none;
  border-color: rgba(31, 122, 122, 0.34);
  box-shadow: 0 0 0 4px rgba(31, 122, 122, 0.12);
}
.table-shell {
  overflow: auto;
  border-radius: 1.2rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.8);
}
.table-shell--wide {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}
.data-table {
  width: 100%;
  min-width: 640px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.94rem;
}
.data-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  text-align: left;
  padding: 0.82rem 0.78rem;
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.98), rgba(248, 242, 232, 0.98));
  border-bottom: 1px solid var(--line);
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #425761;
}
.data-table td {
  text-align: left;
  padding: 0.82rem 0.78rem;
  border-bottom: 1px solid rgba(18, 39, 48, 0.08);
  vertical-align: top;
}
.data-table tbody tr:nth-child(even) { background: rgba(31, 122, 122, 0.025); }
.data-table tbody tr:hover { background: rgba(202, 109, 44, 0.06); }
.data-table code { overflow-wrap: anywhere; }
.reference-table--vocab {
  min-width: 1460px;
  table-layout: fixed;
}
.reference-table--unit-review {
  min-width: 1260px;
  table-layout: fixed;
}
.reference-table--vocab col.term-col-label { width: 18rem; }
.reference-table--vocab col.term-col-iri { width: 15rem; }
.reference-table--vocab col.term-col-status { width: 7rem; }
.reference-table--vocab col.term-col-class { width: 8rem; }
.reference-table--vocab col.term-col-quantity-kind { width: 13rem; }
.reference-table--vocab col.term-col-unit { width: 9rem; }
.reference-table--vocab col.term-col-alt-labels { width: 17rem; }
.reference-table--vocab col.term-col-definition { width: 22rem; }
.reference-table--vocab col.term-col-mappings { width: 14rem; }
.reference-table--unit-review col.term-col-label { width: 18rem; }
.reference-table--unit-review col.term-col-iri { width: 15rem; }
.reference-table--unit-review col.term-col-class { width: 8rem; }
.reference-table--unit-review col.term-col-quantity-kind { width: 13rem; }
.reference-table--unit-review col.term-col-alt-labels { width: 17rem; }
.reference-table--unit-review col.term-col-decision { width: 12rem; }
.reference-table--unit-review col.term-col-note { width: 24rem; }
.term-cell {
  display: grid;
  gap: 0.45rem;
}
.term-title {
  font-size: 0.96rem;
  font-weight: 700;
  line-height: 1.35;
  color: var(--slate-950);
}
.term-subtle {
  font-size: 0.78rem;
  line-height: 1.45;
  color: var(--muted);
}
.iri-cell code,
.reference-table--unit-review .iri-cell code {
  display: block;
  white-space: normal;
  word-break: break-word;
  line-height: 1.5;
}
.term-chip,
.term-pill-list a,
.term-pill-list span {
  display: inline-flex;
  align-items: center;
  min-height: 1.8rem;
  border-radius: 999px;
  border: 1px solid rgba(18, 39, 48, 0.1);
  background: rgba(255, 255, 255, 0.92);
  padding: 0.2rem 0.62rem;
  font-size: 0.81rem;
  line-height: 1.3;
  color: var(--slate-900);
  text-decoration: none;
}
.term-chip--class {
  background: linear-gradient(180deg, rgba(244, 251, 251, 0.94), rgba(255, 247, 236, 0.94));
}
.term-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: flex-start;
}
.term-pill-list--muted span {
  color: var(--muted);
  background: rgba(18, 39, 48, 0.04);
}
.term-stack {
  display: grid;
  gap: 0.38rem;
}
.term-stack span,
.term-stack a {
  display: block;
  line-height: 1.45;
}
.term-copy {
  max-width: 36ch;
  line-height: 1.58;
  color: #223740;
}
.term-copy--wide {
  max-width: 48ch;
}
.term-note {
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--muted);
}
.cell-status,
.cell-class {
  white-space: nowrap;
}
.prose { font-size: 1rem; }
.prose p,
.prose li { max-width: 72ch; }
.prose h3 { margin-top: 1.25rem; }
.prose details {
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid var(--line);
  border-radius: 1rem;
  padding: 0.85rem 1rem;
  margin: 0.75rem 0;
}
.prose summary {
  cursor: pointer;
  font-weight: 700;
}
.footer {
  color: var(--muted);
  font-size: 0.92rem;
  padding-top: 1rem;
}
.footer p {
  margin: 0;
}
.footer-funding {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 1rem 1.25rem;
  align-items: center;
  margin-top: 1rem;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(18, 39, 48, 0.08);
  border-radius: 1.3rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 252, 0.94));
  box-shadow: 0 18px 48px rgba(18, 39, 48, 0.08);
}
.footer-funding__brand {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  color: inherit;
  text-decoration: none;
}
.footer-funding__brand svg {
  width: min(100%, 220px);
  height: auto;
  display: block;
}
.footer-funding__copy {
  display: grid;
  gap: 0.35rem;
  color: var(--ink);
}
.footer-funding__copy p {
  margin: 0;
  max-width: 72ch;
}
.footer-funding__copy a {
  color: var(--teal-700);
  font-weight: 700;
}
.footer-funding__eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.73rem;
  font-weight: 700;
  color: var(--copper-500);
}
@media (max-width: 980px) {
  .hero__grid,
  .landing-grid,
  .home-showcase { grid-template-columns: 1fr; }
  .nav-shell { position: static; }
  .nav { border-radius: 1.75rem; }
  .footer-funding { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  body::before,
  body::after { display: none; }
  h1 { font-size: clamp(2.45rem, 12vw, 3.8rem); }
  .hero__content,
  .hero__panel,
  .card,
  .query-card,
  .diagram-card,
  .check-card { padding: 1rem; }
  .action-row a {
    width: 100%;
    text-align: center;
  }
  .hero-fact-grid { grid-template-columns: 1fr; }
  .data-table { min-width: 560px; }
  .query-toolbar { flex-direction: column; align-items: stretch; }
  .query-toolbar .copy-button,
  .query-toolbar .filter-input { width: 100%; }
  .query-source-grid { grid-template-columns: 1fr; }
  .home-showcase__caption { flex-direction: column; }
}
"""

SITE_JS = """
document.querySelectorAll("[data-table-filter]").forEach((input) => {
  const table = document.getElementById(input.dataset.tableFilter);
  if (!table) return;
  input.addEventListener("input", () => {
    const needle = input.value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.style.display = row.textContent.toLowerCase().includes(needle) ? "" : "none";
    });
  });
});

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.textContent);
      const label = button.textContent;
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = label; }, 1200);
    } catch (error) {
      button.textContent = "Copy failed";
      setTimeout(() => { button.textContent = "Copy query"; }, 1200);
    }
  });
});
"""


_EXPLORER_CATEGORY_STYLES: dict[str, dict[str, str | int]] = {
    "Ontology": {"color": "#7c3aed", "size": 30},
    "Class": {"color": "#2563eb", "size": 24},
    "ObjectProperty": {"color": "#dc2626", "size": 20},
    "DatatypeProperty": {"color": "#059669", "size": 20},
    "AnnotationProperty": {"color": "#0891b2", "size": 18},
    "Individual": {"color": "#0f766e", "size": 16},
    "BlankNode": {"color": "#6b7280", "size": 12},
    "External": {"color": "#a16207", "size": 14},
    "Other": {"color": "#64748b", "size": 12},
}

_EXPLORER_SCHEMA_PREDICATES = {
    RDFS.subClassOf,
    RDFS.subPropertyOf,
    RDFS.domain,
    RDFS.range,
    OWL.inverseOf,
    OWL.equivalentClass,
    OWL.equivalentProperty,
    OWL.sameAs,
    SKOS.exactMatch,
    SKOS.closeMatch,
    SKOS.relatedMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
}

_EXPLORER_EXCLUDED_PREDICATES = {
    RDFS.isDefinedBy,
    DCTERMS.license,
    DCTERMS.source,
    OWL.versionIRI,
}

_EXPLORER_PROVENANCE_PREDICATES = {
    URIRef("http://www.w3.org/ns/prov#used"),
    URIRef("http://www.w3.org/ns/prov#wasGeneratedBy"),
}


def _load_optional_graph(path: Path) -> Graph:
    if not path.exists():
        return Graph()
    try:
        return load_graph(path)
    except Exception:
        return Graph()


def _node_identifier(node: Any) -> str | None:
    if isinstance(node, URIRef):
        return str(node)
    return None


def _qname_or_local(graph: Graph, node: URIRef) -> str:
    try:
        return graph.qname(node)
    except Exception:
        return local_name(str(node))


def _graph_node_label(graph: Graph, node: Any) -> str:
    if isinstance(node, BNode):
        return f"blank:{str(node)[:8]}"
    label = _graph_text(graph, node, [RDFS.label, SKOS.prefLabel, DCTERMS.title])
    if label:
        return label
    fallback = _qname_or_local(graph, node)
    if isinstance(node, URIRef):
        prefix, separator, _ = fallback.partition(":")
        if (separator and prefix.startswith("ns") and prefix[2:].isdigit()) or str(node).startswith("file:///"):
            return humanize_identifier(local_name(str(node)))
    return fallback


def _graph_node_description(graph: Graph, node: Any) -> str:
    if not isinstance(node, URIRef):
        return "Blank node content generated from the release graph."
    return _graph_text(graph, node, [SKOS.definition, RDFS.comment, DCTERMS.description, DCTERMS.abstract]) or "No definition or comment recorded."


def _namespace_for_iri(iri: str) -> str:
    if "#" in iri:
        return iri.rsplit("#", 1)[0] + "#"
    if "/" in iri:
        return iri.rsplit("/", 1)[0] + "/"
    return iri


def _is_local_uri(iri: str, namespace_policy: dict[str, Any]) -> bool:
    prefixes = {
        _clean_text(namespace_policy.get("preferred_namespace_uri", "")),
        _clean_text(namespace_policy.get("term_namespace", "")),
        _clean_text(namespace_policy.get("ontology_iri", "")),
        _clean_text(namespace_policy.get("public_html_base", "")),
    }
    return any(prefix and iri.startswith(prefix) for prefix in prefixes)


def _explorer_edge_family(
    predicate: URIRef,
    object_properties: set[Any],
    namespace_policy: dict[str, Any],
) -> str:
    predicate_iri = str(predicate)
    if predicate == RDF.type:
        return "type"
    if predicate in _EXPLORER_SCHEMA_PREDICATES:
        return "schema"
    if predicate in _EXPLORER_EXCLUDED_PREDICATES:
        return ""
    if predicate == QUDT.unit:
        return "unit"
    if predicate == QUDT.quantityKind:
        return "quantity_kind"
    if predicate in _EXPLORER_PROVENANCE_PREDICATES:
        return "provenance"
    if predicate in object_properties:
        return "object_property"
    if _is_local_uri(predicate_iri, namespace_policy):
        return "relation"
    if predicate_iri.startswith("http://qudt.org/schema/qudt/"):
        return "qudt"
    return ""


def _node_category(
    node: Any,
    classes: set[Any],
    object_properties: set[Any],
    datatype_properties: set[Any],
    annotation_properties: set[Any],
    ontologies: set[Any],
    individuals: set[Any],
    namespace_policy: dict[str, Any],
) -> str:
    if isinstance(node, BNode):
        return "BlankNode"
    if node in ontologies:
        return "Ontology"
    if node in classes:
        return "Class"
    if node in object_properties:
        return "ObjectProperty"
    if node in datatype_properties:
        return "DatatypeProperty"
    if node in annotation_properties:
        return "AnnotationProperty"
    if node in individuals:
        return "Individual"
    if isinstance(node, URIRef) and not _is_local_uri(str(node), namespace_policy):
        return "External"
    return "Other"


def _build_graph_explorer_payload(
    module_rows: list[dict[str, Any]],
    namespace_policy: dict[str, Any],
    profile_label: str,
) -> dict[str, Any]:
    combined = Graph()
    node_objects: dict[str, Any] = {}
    node_modules: dict[str, set[str]] = {}
    triples_preview: list[dict[str, Any]] = []
    preview_budget = 520

    for row in module_rows:
        graph: Graph = row["graph"]
        module_id = row["id"]
        for triple in graph:
            combined.add(triple)
            subject, predicate, obj = triple
            subject_id = _node_identifier(subject)
            if subject_id:
                node_objects.setdefault(subject_id, subject)
                node_modules.setdefault(subject_id, set()).add(module_id)
            object_id = _node_identifier(obj)
            if object_id:
                node_objects.setdefault(object_id, obj)
                node_modules.setdefault(object_id, set()).add(module_id)
            if len(triples_preview) < preview_budget:
                triples_preview.append(
                    {
                        "module": module_id,
                        "subject": str(subject),
                        "predicate": str(predicate),
                        "object": str(obj),
                        "subject_label": _graph_node_label(combined, subject) if isinstance(subject, (URIRef, BNode)) else _clean_text(subject),
                        "predicate_label": _qname_or_local(combined, predicate),
                        "object_label": _graph_node_label(combined, obj) if isinstance(obj, (URIRef, BNode)) else _clean_text(obj),
                        "object_is_literal": isinstance(obj, Literal),
                    }
                )

    classes = set(combined.subjects(RDF.type, OWL.Class)) | set(combined.subjects(RDF.type, RDFS.Class))
    object_properties = set(combined.subjects(RDF.type, OWL.ObjectProperty))
    datatype_properties = set(combined.subjects(RDF.type, OWL.DatatypeProperty))
    annotation_properties = set(combined.subjects(RDF.type, OWL.AnnotationProperty))
    ontologies = set(combined.subjects(RDF.type, OWL.Ontology))
    typed_nodes = {subject for subject, _, _ in combined.triples((None, RDF.type, None)) if isinstance(subject, (URIRef, BNode))}
    individuals = typed_nodes.difference(classes | object_properties | datatype_properties | annotation_properties | ontologies)

    for node in classes | object_properties | datatype_properties | annotation_properties | ontologies | individuals:
        node_id = _node_identifier(node)
        if not node_id:
            continue
        node_objects.setdefault(node_id, node)
        node_modules.setdefault(node_id, set())

    nodes: list[dict[str, Any]] = []
    for node_id, node in node_objects.items():
        category = _node_category(
            node,
            classes,
            object_properties,
            datatype_properties,
            annotation_properties,
            ontologies,
            individuals,
            namespace_policy,
        )
        style = _EXPLORER_CATEGORY_STYLES.get(category, _EXPLORER_CATEGORY_STYLES["Other"])
        iri = str(node) if isinstance(node, URIRef) else node_id
        nodes.append(
            {
                "id": node_id,
                "iri": iri,
                "localName": local_name(iri) if isinstance(node, URIRef) else node_id,
                "name": _graph_node_label(combined, node),
                "qname": _qname_or_local(combined, node) if isinstance(node, URIRef) else node_id,
                "value": iri,
                "category": category,
                "description": _graph_node_description(combined, node),
                "modules": sorted(node_modules.get(node_id, set())),
                "local": True if isinstance(node, BNode) else _is_local_uri(iri, namespace_policy),
                "namespace": _namespace_for_iri(iri) if isinstance(node, URIRef) else "_:blank-node",
                "symbolSize": int(style["size"]),
                "color": str(style["color"]),
            }
        )
    nodes.sort(key=lambda row: (row["name"].lower(), row["id"]))

    links: list[dict[str, Any]] = []
    seen_links: set[tuple[str, str, str, str, str]] = set()
    for row in module_rows:
        graph = row["graph"]
        module_id = row["id"]
        for subject, predicate, obj in graph:
            subject_id = _node_identifier(subject)
            object_id = _node_identifier(obj)
            if not subject_id or not object_id:
                continue
            edge_family = _explorer_edge_family(predicate, object_properties, namespace_policy)
            if not edge_family:
                continue
            key = (subject_id, str(predicate), object_id, module_id, edge_family)
            if key in seen_links:
                continue
            seen_links.add(key)
            links.append(
                {
                    "source": subject_id,
                    "target": object_id,
                    "value": _qname_or_local(combined, predicate),
                    "predicate": str(predicate),
                    "module": module_id,
                    "edgeFamily": edge_family,
                }
            )
    links.sort(key=lambda row: (row["module"], row["edgeFamily"], row["value"], row["source"], row["target"]))

    degree_counts: dict[str, int] = {}
    for link in links:
        degree_counts[link["source"]] = degree_counts.get(link["source"], 0) + 1
        degree_counts[link["target"]] = degree_counts.get(link["target"], 0) + 1
    for node in nodes:
        node["degree"] = degree_counts.get(node["id"], 0)

    module_summaries: list[dict[str, Any]] = []
    for row in module_rows:
        module_id = row["id"]
        module_summaries.append(
            {
                "id": module_id,
                "label": row["label"],
                "description": row["description"],
                "path": row["path"],
                "fallback": row.get("fallback", ""),
                "default": bool(row.get("default", False)),
                "triple_count": len(row["graph"]),
                "node_count": sum(1 for node in nodes if module_id in node["modules"]),
                "edge_count": sum(1 for link in links if link["module"] == module_id),
            }
        )

    return {
        "profile_label": profile_label,
        "overview": {
            "profile_label": profile_label,
            "node_count": len(nodes),
            "edge_count": len(links),
            "module_count": len(module_rows),
            "local_node_count": sum(1 for node in nodes if node["local"]),
            "external_node_count": sum(1 for node in nodes if not node["local"]),
            "triple_count": sum(len(row["graph"]) for row in module_rows),
        },
        "categories": [
            {"name": name, "color": str(style["color"])}
            for name, style in _EXPLORER_CATEGORY_STYLES.items()
        ],
        "modules": module_summaries,
        "nodes": nodes,
        "links": links,
        "triples": triples_preview,
    }


def _graph_text(graph: Graph, subject: URIRef, predicates: list[URIRef]) -> str:
    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            return _clean_text(obj)
    return ""


def _mapping_lookup(review_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for row in review_rows:
        if not row.get("target_iri"):
            continue
        lookup.setdefault(row["local_iri"], []).append(f"{_clean_text(row['relation'])} -> {_clean_text(row['target_label'])}")
    return lookup


def _term_class_label(term: Any) -> str:
    generic = {
        "Thing",
        "Resource",
        "NamedIndividual",
        "Ontology",
        "Class",
        "ObjectProperty",
        "DatatypeProperty",
        "AnnotationProperty",
        "Concept",
    }
    candidates: list[str] = []
    for value in list(getattr(term, "types", [])) + list(getattr(term, "superclasses", [])):
        name = _clean_text(local_name(value))
        if not name or name in generic:
            continue
        humanized = humanize_identifier(name)
        if humanized not in candidates:
            candidates.append(humanized)
    if candidates:
        return candidates[0]
    if getattr(term, "category", "") == "controlled_vocabulary_term":
        return "Controlled term"
    return _clean_text(getattr(term, "term_type", "")).replace("_", " ") or "Unspecified"


def _append_unit_rows(graph: Graph, subject: Any, rows: list[dict[str, str]], seen: set[str]) -> None:
    for predicate, unit in graph.predicate_objects(subject):
        if predicate != QUDT.unit and local_name(predicate) not in {"unit", "hasUnit"}:
            continue
        unit_iri = str(unit)
        label = (
            _graph_text(graph, unit, [RDFS.label, SKOS.prefLabel])
            if isinstance(unit, URIRef)
            else _clean_text(unit)
        ) or humanize_identifier(local_name(unit))
        key = f"{unit_iri}|{label}"
        if key in seen:
            continue
        seen.add(key)
        is_qudt_unit = unit_iri.startswith("http://qudt.org/") or unit_iri.startswith("https://qudt.org/")
        rows.append(
            {
                "label": label,
                "iri": unit_iri if isinstance(unit, URIRef) else "",
                "html": _href_html(unit_iri, label) if is_qudt_unit else escape(label),
            }
        )


def _append_quantity_kind_rows(graph: Graph, subject: Any, rows: list[dict[str, str]], seen: set[str]) -> None:
    for predicate, quantity_kind in graph.predicate_objects(subject):
        if predicate != QUDT.quantityKind and local_name(predicate) not in {"quantityKind", "hasQuantityKind"}:
            continue
        quantity_kind_iri = str(quantity_kind)
        label = (
            _graph_text(graph, quantity_kind, [RDFS.label, SKOS.prefLabel])
            if isinstance(quantity_kind, URIRef)
            else _clean_text(quantity_kind)
        ) or humanize_identifier(local_name(quantity_kind))
        key = f"{quantity_kind_iri}|{label}"
        if key in seen:
            continue
        seen.add(key)
        is_qudt_quantity_kind = quantity_kind_iri.startswith("http://qudt.org/") or quantity_kind_iri.startswith("https://qudt.org/")
        rows.append(
            {
                "label": label,
                "iri": quantity_kind_iri if isinstance(quantity_kind, URIRef) else "",
                "html": _href_html(quantity_kind_iri, label) if is_qudt_quantity_kind else escape(label),
            }
        )


def _term_units(graph: Graph, term_iri: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    subject = URIRef(term_iri)
    _append_unit_rows(graph, subject, rows, seen)
    quantity_nodes = [
        obj
        for predicate, obj in graph.predicate_objects(subject)
        if local_name(predicate) in {"hasQuantityValue", "quantityValue"}
    ]
    for quantity_node in quantity_nodes:
        _append_unit_rows(graph, quantity_node, rows, seen)
    rows.sort(key=lambda row: (_clean_text(row["label"]).lower(), _clean_text(row["iri"])))
    return rows


def _term_quantity_kinds(graph: Graph, term_iri: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    subject = URIRef(term_iri)
    _append_quantity_kind_rows(graph, subject, rows, seen)
    quantity_nodes = [
        obj
        for predicate, obj in graph.predicate_objects(subject)
        if local_name(predicate) in {"hasQuantityValue", "quantityValue"}
    ]
    for quantity_node in quantity_nodes:
        _append_quantity_kind_rows(graph, quantity_node, rows, seen)
    rows.sort(key=lambda row: (_clean_text(row["label"]).lower(), _clean_text(row["iri"])))
    return rows


def _term_alternative_labels(graph: Graph, term_iri: str, primary_label: str) -> list[str]:
    subject = URIRef(term_iri)
    seen: set[str] = set()
    labels: list[str] = []
    for predicate in (SKOS.altLabel, SKOS.prefLabel):
        for obj in graph.objects(subject, predicate):
            text = _clean_text(obj)
            if not text or text == _clean_text(primary_label) or text in seen:
                continue
            seen.add(text)
            labels.append(text)
    return sorted(labels, key=str.lower)


def _term_row(
    term: Any,
    mapping_lookup: dict[str, list[str]],
    namespace_policy: dict[str, Any],
    graph: Graph,
) -> dict[str, str]:
    unit_rows = _term_units(graph, term.iri)
    quantity_kind_rows = _term_quantity_kinds(graph, term.iri)
    alternative_labels = _term_alternative_labels(graph, term.iri, _clean_text(term.label))
    return {
        "label": _clean_text(term.label),
        "iri": term.iri,
        "definition": _clean_text(term.definition or term.comment or "No definition recorded."),
        "deprecated": "Deprecated" if getattr(term, "deprecated", False) else "Active",
        "superclasses": ", ".join(_clean_values(term.superclasses)) or "None",
        "superclasses_html": _external_value_list_html(term.superclasses, namespace_policy),
        "mappings": ", ".join(_clean_values(mapping_lookup.get(term.iri, []))) or "None",
        "kind": _clean_text(term.term_type).replace("_", " "),
        "class_label": _term_class_label(term),
        "domain": ", ".join(_clean_values(term.domains)) or "None",
        "domain_html": _external_value_list_html(term.domains, namespace_policy),
        "range": ", ".join(_clean_values(term.ranges)) or "None",
        "range_html": _external_value_list_html(term.ranges, namespace_policy),
        "quantity_kinds": ", ".join(row["label"] for row in quantity_kind_rows) or "—",
        "quantity_kinds_html": ", ".join(row["html"] for row in quantity_kind_rows) or "—",
        "units": ", ".join(row["label"] for row in unit_rows) or "—",
        "units_html": ", ".join(row["html"] for row in unit_rows) or "—",
        "alternative_labels": ", ".join(alternative_labels) or "—",
        "alternative_labels_html": ", ".join(escape(label) for label in alternative_labels) or "—",
        "anchor": local_name(term.iri),
    }


def _term_row_view(
    term: Any,
    mapping_lookup: dict[str, list[str]],
    namespace_policy: dict[str, Any],
    graph: Graph,
) -> dict[str, str]:
    row = _term_row(term, mapping_lookup, namespace_policy, graph)
    mapping_values = _clean_values(mapping_lookup.get(term.iri, []))
    class_label = row["class_label"]
    row.update(
        {
            "iri_html": _href_html(term.iri, term.iri, code=True) if _is_web_url(term.iri) else f"<code>{escape(term.iri)}</code>",
            "deprecated_html": _status_html(row["deprecated"]),
            "mappings_html": _stack_html(mapping_values),
            "class_label_html": f"<span class='term-chip term-chip--class'>{escape(class_label)}</span>",
            "quantity_kinds_html": _link_pills_html(_term_quantity_kinds(graph, term.iri)),
            "units_html": _link_pills_html(_term_units(graph, term.iri)),
            "alternative_labels_html": _text_pills_html(_term_alternative_labels(graph, term.iri, _clean_text(term.label)), muted=True),
        }
    )
    return row


def _enrich_explorer_nodes(payload: dict[str, Any], detail_rows: list[dict[str, str]]) -> dict[str, Any]:
    detail_lookup = {row["iri"]: row for row in detail_rows}
    for node in payload.get("nodes", []):
        detail = detail_lookup.get(node.get("iri", ""))
        if not detail:
            node["display_class"] = _clean_text(node.get("category", ""))
            node["units"] = ""
            node["mappings_text"] = ""
            node["domain"] = ""
            node["range"] = ""
            node["superclasses"] = ""
            node["deprecated"] = "Active"
            node["search_text"] = " ".join(
                part
                for part in [node.get("name", ""), node.get("localName", ""), node.get("qname", ""), node.get("iri", ""), node.get("description", "")]
                if part
            )
            continue
        node["display_class"] = detail["class_label"]
        node["definition"] = detail["definition"]
        node["description"] = detail["definition"] or node.get("description", "")
        node["units"] = "" if detail["units"] in {"Not specified", "â€”", "—"} else detail["units"]
        node["units_html"] = "" if detail["units"] in {"Not specified", "â€”", "—"} else detail["units_html"]
        node["mappings_text"] = "" if detail["mappings"] == "None" else detail["mappings"]
        node["domain"] = "" if detail["domain"] == "None" else detail["domain"]
        node["range"] = "" if detail["range"] == "None" else detail["range"]
        node["superclasses"] = "" if detail["superclasses"] == "None" else detail["superclasses"]
        node["deprecated"] = detail["deprecated"]
        node["search_text"] = " ".join(
            part
            for part in [
                node.get("name", ""),
                node.get("localName", ""),
                node.get("qname", ""),
                node.get("iri", ""),
                node.get("description", ""),
                node.get("display_class", ""),
                node.get("units", ""),
                node.get("mappings_text", ""),
                node.get("domain", ""),
                node.get("range", ""),
                node.get("superclasses", ""),
            ]
            if part
        )
    return payload


_MOJIBAKE_REPLACEMENTS = {
    "â€“": "-",
    "â€”": "-",
    "â€˜": "'",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "Â ": " ",
    "Â": "",
}


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("â€”", "—").replace("â€“", "-")
    for old, new in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return normalize_space(text)


def _clean_values(values: list[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            rows.append(cleaned)
    return rows


def _public_namespace_rows(inspection_report: dict[str, Any], namespace_policy: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    hidden_local = 0
    synthetic_index = 1
    for row in inspection_report["namespace_rows"]:
        namespace = row["namespace"]
        if namespace.startswith("file:///"):
            hidden_local += int(row["count"])
            continue
        prefix = _clean_text(row.get("prefix", ""))
        if not prefix and namespace == namespace_policy["preferred_namespace_uri"]:
            prefix = namespace_policy["preferred_namespace_prefix"]
        if not prefix:
            prefix = f"ns{synthetic_index}"
            synthetic_index += 1
        rows.append(
            {
                "prefix": prefix,
                "namespace": namespace,
                "count": row["count"],
                "href": namespace if _is_web_url(namespace) and not namespace.startswith(namespace_policy["ontology_iri"]) else "",
            }
        )
    return rows[:18], hidden_local


def _mapping_stats(review_rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = 0
    unmapped = 0
    apply_default = 0
    source_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for row in review_rows:
        if row.get("target_iri"):
            mapped += 1
            source_id = _clean_text(row.get("source_id", "")) or "unspecified"
            relation = _clean_text(row.get("relation", "")) or "unspecified"
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
            if _clean_text(row.get("apply_default", "")).lower() == "yes":
                apply_default += 1
        else:
            unmapped += 1
    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "apply_default": apply_default,
        "sources": [{"label": key, "count": value} for key, value in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))],
        "relations": [{"label": key, "count": value} for key, value in sorted(relation_counts.items(), key=lambda item: (-item[1], item[0]))],
    }


def _load_unit_review_rows(root: Path, vocabulary_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_path = root / "output" / "review" / "unit_evidence_review.csv"
    if not review_path.exists():
        return []
    vocabulary_lookup = {row["iri"]: row for row in vocabulary_rows}
    rows: list[dict[str, str]] = []
    for item in read_csv(review_path):
        decision = _clean_text(item.get("decision", ""))
        if not decision.startswith("review_"):
            continue
        term_iri = _clean_text(item.get("term_iri", ""))
        detail = vocabulary_lookup.get(term_iri)
        if not detail:
            continue
        rows.append(
            {
                "label": detail["label"],
                "iri": term_iri,
                "class_label": detail["class_label"],
                "quantity_kinds_html": detail["quantity_kinds_html"],
                "alternative_labels_html": detail["alternative_labels_html"],
                "decision": decision.replace("_", " "),
                "note": _clean_text(item.get("note", "")) or "Manual review is still required.",
            }
        )
    rows.sort(key=lambda row: (row["label"].lower(), row["decision"]))
    return rows


def _placeholder_definition_count(rows: list[dict[str, str]]) -> int:
    prefixes = (
        "A class in the H2KG ontology release",
        "An object property in the H2KG ontology release",
        "A datatype property in the H2KG ontology release",
        "An annotation property used by the H2KG ontology release",
        "A curated controlled term in the H2KG ontology release",
        "A local ontology term representing",
    )
    return sum(1 for row in rows if row["definition"].startswith(prefixes))


def _status_for_ratio(value: float, good: float, watch: float) -> str:
    if value >= good:
        return "good"
    if value >= watch:
        return "watch"
    return "action"


def _status_for_count(value: int) -> str:
    if value == 0:
        return "good"
    if value <= 5:
        return "watch"
    return "action"


def _status_for_flag(value: bool) -> str:
    return "good" if value else "action"


def _list_html(items: list[str]) -> str:
    return "<ul class='simple-list'>" + "".join(f"<li>{escape(_clean_text(item))}</li>" for item in items) + "</ul>"


def _faq_html(items: list[dict[str, str]]) -> str:
    html = []
    for row in items:
        html.append(
            f"<details><summary>{escape(_clean_text(row['question']))}</summary><p>{escape(_clean_text(row['answer']))}</p></details>"
        )
    return "".join(html)


def _pattern_html(items: list[dict[str, Any]]) -> str:
    cards = []
    for row in items:
        bullets = "".join(f"<li>{escape(_clean_text(item))}</li>" for item in row.get("bullets", []))
        cards.append(
            f"<article class='feature-item'><h3>{escape(_clean_text(row['title']))}</h3><p>{escape(_clean_text(row['description']))}</p><ul class='simple-list'>{bullets}</ul></article>"
        )
    return "<div class='feature-list'>" + "".join(cards) + "</div>"


def _timeline_html(items: list[dict[str, str]]) -> str:
    blocks = []
    for row in items:
        blocks.append(
            f"<div class='timeline__item'><h3>{escape(_clean_text(row['title']))}</h3><p>{escape(_clean_text(row['detail']))}</p></div>"
        )
    return "<div class='timeline'>" + "".join(blocks) + "</div>"


def _simple_svg_card(title: str, subtitle: str, value: str, fill: str) -> str:
    return f"""
<svg viewBox="0 0 320 180" width="100%" role="img" aria-label="{escape(title)}">
  <rect width="320" height="180" rx="28" fill="#ffffff"></rect>
  <rect x="20" y="20" width="280" height="140" rx="24" fill="{fill}" stroke="#cbd5e1"></rect>
  <text x="42" y="62" font-size="16" font-family="Trebuchet MS" fill="#0f172a">{escape(title)}</text>
  <text x="42" y="108" font-size="36" font-family="Trebuchet MS" font-weight="700" fill="#115e59">{escape(value)}</text>
  <text x="42" y="138" font-size="13" font-family="Trebuchet MS" fill="#475569">{escape(subtitle)}</text>
</svg>
"""


def _bar_chart_svg(title: str, rows: list[dict[str, Any]], color: str = "#0f766e") -> str:
    if not rows:
        rows = [{"label": "No data", "count": 0}]
    max_count = max(int(row.get("count", 0)) for row in rows) or 1
    bar_rows = []
    for index, row in enumerate(rows[:8]):
        y = 48 + index * 36
        width = int(360 * int(row.get("count", 0)) / max_count) if max_count else 0
        label = escape(_clean_text(row.get("label", "")))
        count = escape(str(row.get("count", 0)))
        bar_rows.append(
            f"""
  <text x="24" y="{y}" font-size="13" font-family="Trebuchet MS" fill="#0f172a">{label}</text>
  <rect x="180" y="{y - 14}" width="370" height="16" rx="8" fill="#e2e8f0"></rect>
  <rect x="180" y="{y - 14}" width="{width}" height="16" rx="8" fill="{color}"></rect>
  <text x="560" y="{y}" font-size="12" font-family="Trebuchet MS" fill="#475569">{count}</text>
"""
        )
    height = max(180, 72 + len(rows[:8]) * 36)
    return f"""
<svg viewBox="0 0 600 {height}" width="100%" role="img" aria-label="{escape(title)}">
  <rect width="600" height="{height}" rx="24" fill="#ffffff"></rect>
  <text x="24" y="24" font-size="15" font-family="Trebuchet MS" fill="#0f172a">{escape(title)}</text>
  {''.join(bar_rows)}
</svg>
"""


def _import_graph_svg(import_rows: list[dict[str, Any]]) -> str:
    enabled_rows = [row for row in import_rows if row.get("enabled")]
    cards = []
    edges = []
    center_x, center_y = 320, 80
    cards.append(f'<rect x="{center_x - 100}" y="{center_y - 28}" width="200" height="56" rx="18" fill="#ecfeff" stroke="#94a3b8"></rect>')
    cards.append(f'<text x="{center_x}" y="{center_y + 4}" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">Asserted schema module</text>')
    positions = [(70, 200), (240, 200), (410, 200), (580, 200), (155, 300), (325, 300), (495, 300)]
    for row, (x, y) in zip(enabled_rows[:7], positions):
        cards.append(f'<rect x="{x - 70}" y="{y - 24}" width="140" height="48" rx="16" fill="#f8fafc" stroke="#cbd5e1"></rect>')
        cards.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="12" font-family="Trebuchet MS" fill="#0f172a">{escape(_clean_text(row["title"]))}</text>')
        edges.append(f'<line x1="{center_x}" y1="{center_y + 28}" x2="{x}" y2="{y - 28}" stroke="#0f766e" stroke-width="2.5"></line>')
    return f"""
<svg viewBox="0 0 650 360" width="100%" role="img" aria-label="Import graph">
  <rect width="650" height="360" rx="24" fill="#ffffff"></rect>
  {''.join(edges)}
  {''.join(cards)}
  <text x="24" y="336" font-size="12" font-family="Trebuchet MS" fill="#475569">Configured import and alignment source overview for the active release profile.</text>
</svg>
"""


def _process_pattern_svg() -> str:
    return """
<svg viewBox="0 0 760 240" width="100%" role="img" aria-label="Process, data, and provenance pattern">
  <rect width="760" height="240" rx="24" fill="#ffffff"></rect>
  <rect x="40" y="70" width="150" height="56" rx="18" fill="#ecfeff" stroke="#94a3b8"></rect>
  <rect x="300" y="50" width="170" height="64" rx="18" fill="#f0fdf4" stroke="#94a3b8"></rect>
  <rect x="300" y="150" width="170" height="64" rx="18" fill="#fff7ed" stroke="#94a3b8"></rect>
  <rect x="570" y="70" width="150" height="56" rx="18" fill="#fef3c7" stroke="#94a3b8"></rect>
  <text x="115" y="104" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">Material / input</text>
  <text x="385" y="88" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">Measurement / process</text>
  <text x="385" y="188" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">Data / quantity values</text>
  <text x="645" y="104" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">Agent / provenance</text>
  <line x1="190" y1="98" x2="300" y2="82" stroke="#0f766e" stroke-width="3"></line>
  <line x1="385" y1="114" x2="385" y2="150" stroke="#0f766e" stroke-width="3"></line>
  <line x1="470" y1="82" x2="570" y2="98" stroke="#0f766e" stroke-width="3"></line>
  <text x="226" y="78" font-size="12" font-family="Trebuchet MS" fill="#475569">hasInputMaterial</text>
  <text x="398" y="136" font-size="12" font-family="Trebuchet MS" fill="#475569">hasOutputData / hasQuantityValue</text>
  <text x="498" y="76" font-size="12" font-family="Trebuchet MS" fill="#475569">prov:wasAssociatedWith</text>
  <text x="24" y="218" font-size="12" font-family="Trebuchet MS" fill="#475569">Release pattern: keep processes and schema in the asserted module, and publish example data-like nodes separately.</text>
</svg>
"""


def _term_neighborhood_svg(classes: list[dict[str, str]], properties: list[dict[str, str]]) -> str:
    focus = next((row for row in classes if "measurement" in row["label"].lower()), classes[0] if classes else None)
    if focus is None:
        return _simple_svg_card("Neighborhood unavailable", "No class rows were available for visualization.", "0", "#f8fafc")
    related = [row for row in properties if focus["iri"] in {row["domain"], row["range"]} or focus["label"].lower() in row["domain"].lower()]
    related = related[:6]
    cards = [
        '<rect x="280" y="80" width="200" height="56" rx="18" fill="#ecfeff" stroke="#94a3b8"></rect>',
        f'<text x="380" y="114" text-anchor="middle" font-size="14" font-family="Trebuchet MS" fill="#0f172a">{escape(focus["label"])}</text>',
    ]
    positions = [(120, 40), (120, 170), (380, 190), (640, 170), (640, 40), (380, 10)]
    edges = []
    for row, (x, y) in zip(related, positions):
        cards.append(f'<rect x="{x - 90}" y="{y}" width="180" height="44" rx="16" fill="#f8fafc" stroke="#cbd5e1"></rect>')
        cards.append(f'<text x="{x}" y="{y + 26}" text-anchor="middle" font-size="12" font-family="Trebuchet MS" fill="#0f172a">{escape(_clean_text(row["label"]))}</text>')
        edges.append(f'<line x1="380" y1="108" x2="{x}" y2="{y + 22}" stroke="#0f766e" stroke-width="2.5"></line>')
    return f"""
<svg viewBox="0 0 760 260" width="100%" role="img" aria-label="Term neighborhood">
  <rect width="760" height="260" rx="24" fill="#ffffff"></rect>
  {''.join(edges)}
  {''.join(cards)}
  <text x="24" y="236" font-size="12" font-family="Trebuchet MS" fill="#475569">Property neighborhood preview around a representative measurement-focused class.</text>
</svg>
"""


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    header_html = "".join(f"<th>{escape(item)}</th>" for item in headers)
    row_html = []
    for row in rows:
        row_html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table class='data-table'><thead><tr>{header_html}</tr></thead><tbody>{''.join(row_html)}</tbody></table>"


def _is_web_url(value: str) -> bool:
    text = _clean_text(value)
    return text.startswith("https://") or text.startswith("http://")


def _href_html(href: str, label: str | None = None, code: bool = False) -> str:
    target = _clean_text(href)
    text = _clean_text(label or href)
    inner = f"<code>{escape(text)}</code>" if code else escape(text)
    return f"<a href='{escape(target, quote=True)}'>{inner}</a>"


def _pill_list_html(items: list[str], modifier: str = "") -> str:
    if not items:
        return "<span class='term-note'>—</span>"
    class_name = "term-pill-list"
    if modifier:
        class_name = f"{class_name} {modifier}"
    return f"<div class='{class_name}'>{''.join(items)}</div>"


def _text_pills_html(values: list[str], muted: bool = False) -> str:
    clean = [value for value in _clean_values(values) if value and value not in {"—", "â€”"}]
    items = [f"<span>{escape(value)}</span>" for value in clean]
    modifier = "term-pill-list--muted" if muted else ""
    return _pill_list_html(items, modifier)


def _link_pills_html(rows: list[dict[str, str]]) -> str:
    items: list[str] = []
    for row in rows:
        html = row.get("html", "")
        if not html:
            continue
        items.append(html if html.startswith("<span") else f"<span>{html}</span>")
    return _pill_list_html(items)


def _stack_html(values: list[str], empty: str = "None") -> str:
    clean = [value for value in _clean_values(values) if value and value != empty]
    if not clean:
        return f"<span class='term-note'>{escape(empty)}</span>"
    return "<div class='term-stack'>" + "".join(f"<span>{escape(value)}</span>" for value in clean) + "</div>"


def _status_html(label: str) -> str:
    text = _clean_text(label)
    css = "status-good" if text == "Active" else "status-watch"
    return f"<span class='status-pill {css}'>{escape(text)}</span>"


def _external_value_list_html(values: list[str], namespace_policy: dict[str, Any]) -> str:
    rendered: list[str] = []
    for value in _clean_values(values):
        if _is_web_url(value) and not value.startswith(namespace_policy["ontology_iri"]):
            rendered.append(_href_html(value, value, code=True))
        elif _is_web_url(value):
            rendered.append(f"<code>{escape(value)}</code>")
        else:
            rendered.append(escape(value))
    return ", ".join(rendered) or "None"


def build_docs(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    examples_graph: Graph,
    review_rows: list[dict[str, Any]],
    inspection_report: dict[str, Any],
    validation_report: dict[str, Any],
    fair_scores: dict[str, Any],
    classifications: dict[str, Any],
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    source_registry: dict[str, Any],
    namespace_policy_raw: dict[str, Any],
    root: Path,
) -> None:
    output_dir = root / "output" / "docs"
    pages_dir = ensure_dir(output_dir / "pages")
    assets_dir = ensure_dir(output_dir / "assets")
    data_dir = ensure_dir(output_dir / "data")

    env = Environment(loader=FileSystemLoader(str(root / "templates" / "site")))
    documentation_cfg = release_profile.get("documentation", {})
    resources_cfg = documentation_cfg.get("resources", {})
    split_report = read_json(root / "output" / "reports" / "split_report.json")
    metadata_report = read_json(root / "output" / "reports" / "metadata_report.json")
    import_catalog = read_json(root / "output" / "reports" / "import_catalog.json") if (root / "output" / "reports" / "import_catalog.json").exists() else []
    changelog_payload = read_json(root / "output" / "reports" / "changelog_report.json") if (root / "output" / "reports" / "changelog_report.json").exists() else {"entries": []}
    citation_meta = load_yaml(root / "CITATION.cff") if (root / "CITATION.cff").exists() else {}
    zenodo_meta = read_json(root / ".zenodo.json") if (root / ".zenodo.json").exists() else {}
    profile_label = _clean_text(documentation_cfg.get("profile_label", "Ontology Profile"))
    profile_heading = _clean_text(documentation_cfg.get("profile_heading", f"{profile_label} Ontology Profile"))
    profile_intro = _clean_text(documentation_cfg.get("landing_intro", ""))
    platform_title = _clean_text(release_profile["project"]["title"])
    profile_switch = documentation_cfg.get("profile_switch", [])
    hmc_url = "https://helmholtz-metadaten.de/"
    aimworks_project_url = "https://helmholtz-metadaten.de/inf-projects/aimworks"
    hero_note = _clean_text(
        documentation_cfg.get(
            "hero_note",
            f"An EMMO-aligned application ontology release profile for {profile_label} concepts, measurements, curated vocabulary, and publication-ready provenance.",
        )
    )
    site = {
        "title": _clean_text(release_profile["project"]["title"]),
        "subtitle": _clean_text(release_profile["project"]["subtitle"]),
        "tagline": _clean_text(documentation_cfg["site_tagline"]),
        "version": release_profile["release"]["version"],
        "license_label": _clean_text(release_profile["release"]["ontology_license"]),
        "prefix": namespace_policy["preferred_namespace_prefix"],
        "hero_note": hero_note,
        "hero_facts": [
            {"label": "Profile", "value": profile_label},
            {"label": "Release", "value": str(release_profile["release"]["version"])},
            {"label": "Namespace", "value": namespace_policy["preferred_namespace_prefix"]},
            {"label": "Validation", "value": validation_report["overall_status"].upper()},
            {"label": "FAIR score", "value": str(fair_scores["overall"])},
        ],
        "profile_switch": profile_switch,
        "profile_label": profile_label,
        "nav": [
            {"href": "index.html", "label": "Home"},
            {"href": "pages/visualizations.html", "label": "Explore"},
            {"href": release_profile["publication"]["reference_page"], "label": "Reference"},
            {"href": "pages/user-guide.html", "label": "Guide"},
            {"href": "pages/quality-dashboard.html", "label": "Quality"},
            {"href": "pages/release.html", "label": "Release"},
        ],
        "actions": [
            {"href": "pages/visualizations.html", "label": "Explore ontology", "primary": True},
            {"href": release_profile["publication"]["reference_page"], "label": "Browse reference", "primary": False},
            {"href": "pages/release.html", "label": "Release artifacts", "primary": False},
        ],
    }
    write_text(assets_dir / "site.css", SITE_CSS)
    write_text(assets_dir / "site.js", SITE_JS)
    write_text(assets_dir / "visuals.css", (root / "templates" / "site" / "assets" / "visuals.css").read_text(encoding="utf-8"))
    write_text(assets_dir / "visuals.js", (root / "templates" / "site" / "assets" / "term-finder.js").read_text(encoding="utf-8"))
    copy_file(root / "templates" / "site" / "assets" / "hmc-logo.svg", assets_dir / "hmc-logo.svg")
    graph_poster = {"available": False, "href": "", "alt": "", "caption": ""}
    poster_source = root / "input" / "final poster gephi.png"
    if poster_source.exists():
        poster_target = assets_dir / "knowledge-graph-poster.png"
        copy_file(poster_source, poster_target)
        graph_poster = {
            "available": True,
            "href": "assets/knowledge-graph-poster.png",
            "alt": f"Gephi visualization of the {profile_label} H2KG knowledge graph",
            "caption": "Poster-scale Gephi rendering of the connected H2KG knowledge graph.",
        }
    write_text(output_dir / ".nojekyll", "")

    mapping_lookup = _mapping_lookup(review_rows)
    schema_terms = extract_local_terms(schema_graph, namespace_policy, classifications)
    vocabulary_terms = extract_local_terms(controlled_vocabulary_graph, namespace_policy, classifications)
    vocabulary_context_graph = Graph()
    for triple in schema_graph:
        vocabulary_context_graph.add(triple)
    for triple in controlled_vocabulary_graph:
        vocabulary_context_graph.add(triple)
    for triple in examples_graph:
        vocabulary_context_graph.add(triple)
    classes = [_term_row_view(term, mapping_lookup, namespace_policy, schema_graph) for term in schema_terms if term.term_type == "class"]
    properties = [_term_row_view(term, mapping_lookup, namespace_policy, schema_graph) for term in schema_terms if term.term_type != "class"]
    vocabulary_rows = [_term_row_view(term, mapping_lookup, namespace_policy, vocabulary_context_graph) for term in vocabulary_terms]
    classes.sort(key=lambda item: item["label"].lower())
    properties.sort(key=lambda item: item["label"].lower())
    vocabulary_rows.sort(key=lambda item: item["label"].lower())
    unit_review_rows = _load_unit_review_rows(root, vocabulary_rows)

    ontology_node = find_ontology_node(schema_graph, namespace_policy) or URIRef(namespace_policy["ontology_iri"])
    creators = _clean_values([str(obj) for obj in schema_graph.objects(ontology_node, DCTERMS.creator)])
    contributors = _clean_values([str(obj) for obj in schema_graph.objects(ontology_node, DCTERMS.contributor)])
    imports = _clean_values([str(obj) for obj in schema_graph.objects(ontology_node, OWL.imports)])
    namespace_rows, hidden_local_namespace_count = _public_namespace_rows(inspection_report, namespace_policy)
    mapping_stats = _mapping_stats(review_rows)
    placeholder_definition_count = _placeholder_definition_count(classes + properties + vocabulary_rows)
    baseline_definition_coverage = float(inspection_report.get("definition_coverage", 0.0))

    overview = {
        "description": _graph_text(schema_graph, ontology_node, [DCTERMS.description, DCTERMS.abstract]) or profile_intro,
        "landing_intro": profile_intro,
        "ontology_iri": namespace_policy["ontology_iri"],
        "namespace_mode": namespace_policy["namespace_mode"],
        "schema_term_count": len(classes) + len(properties),
        "vocabulary_count": len(vocabulary_rows),
        "example_count": split_report.get("example_subject_count", 0),
        "release_date": release_profile["release"]["release_date"],
    }
    cards = [
        {"title": "Alignment Stack", "body": "Primary semantic anchors are EMMO, ECHO, QUDT, ChEBI, PROV-O, Dublin Core Terms, and VANN."},
        {"title": "IRI Policy", "body": f"The {profile_label} profile preserves existing local IRIs by default unless namespace migration is explicitly enabled."},
        {"title": "Release Assets", "body": f"The {platform_title} publication includes RDF modules, static docs, versioned endpoints, FAIR reports, validation outputs, and w3id templates."},
    ]
    highlights = [
        {"label": "Schema terms", "value": str(len(classes) + len(properties)), "detail": "Asserted local classes and properties published as the schema module."},
        {"label": "Controlled vocabulary", "value": str(len(vocabulary_rows)), "detail": "Curated named terms kept outside the asserted schema."},
        {"label": "Examples separated", "value": str(split_report.get("example_subject_count", 0)), "detail": "Example or data-like resources removed from the schema module."},
        {"label": "Mapped rows", "value": str(mapping_stats["mapped"]), "detail": "Review rows that have a target IRI in the mapping review output."},
        {"label": "FAIR score", "value": str(fair_scores["overall"]), "detail": "Aggregate pre-publication FAIR readiness signal."},
        {"label": "Validation", "value": validation_report["overall_status"].upper(), "detail": "Current release validation state."},
    ]
    featured_pages = [
        {"href": "pages/visualizations.html", "title": "Explore", "body": "Search the ontology, pick a seed term, and expand the graph progressively without dropping users into a full release dump."},
        {"href": release_profile["publication"]["reference_page"], "title": "Reference", "body": "Browse the full ontology reference with labels, definitions, mappings, units, and module-aware term details."},
        {"href": "pages/user-guide.html", "title": "Guide", "body": "Start with the practical workflow, then branch into scope, modeling patterns, import guidance, and worked examples only when needed."},
        {"href": "pages/quality-dashboard.html", "title": "Quality", "body": "Combines FAIR, validation, metadata hygiene, and publication checks in one place."},
        {"href": "pages/release.html", "title": "Release", "body": "Summarizes publication endpoints, files, provenance, and release bundle outputs."},
        {"href": "pages/queries.html", "title": "Advanced SPARQL", "body": "Power-user query console with competency-question presets for direct browser-side SPARQL execution."},
    ]
    fair_dimension_signals = [
        {
            "label": f"{row.get('acronym', row['dimension'][:1])} / {row['dimension']}",
            "value": f"{row['score']} / 100",
            "status": _status_for_ratio(float(row["score"]) / 100.0, 0.85, 0.7),
            "detail": f"Separated {row.get('acronym', row['dimension'][:1])} component of the FAIR readiness score.",
        }
        for row in fair_scores["dimensions"]
    ]
    external_scores = fair_scores.get("external_scores", {})
    foops_external = external_scores.get("foops", {})
    oops_external = external_scores.get("oops", {})
    transparency_signals = [
        {
            "label": row["label"],
            "value": row["status"],
            "status": "good" if row["status"] in {"reachable", "assessed"} else "watch",
            "detail": (
                f"{row['details']} "
                + (
                    f"Service: {_href_html(row['service_url'], row['service_url'], code=True)}. "
                    if row.get("service_url")
                    else ""
                )
                + (
                    f"Catalogue: {_href_html(row['catalogue_url'], row['catalogue_url'], code=True)}. "
                    if row.get("catalogue_url")
                    else ""
                )
                + "Not counted in the numeric F/A/I/R score."
            ),
        }
        for row in fair_scores.get("transparency_checks", [])
    ]
    external_fair_rows: list[dict[str, str]] = []
    if foops_external.get("overall_score") is not None:
        external_fair_rows.append(
            {
                "label": "FOOPS! overall",
                "value": f"{foops_external['overall_score']} / 100",
                "status": _status_for_ratio(float(foops_external["overall_score"]) / 100.0, 0.85, 0.7),
                "detail": (
                    f"Actual FOOPS! assessment in {foops_external.get('mode', 'unspecified')} mode. "
                    + (
                        f"Validator: {_href_html(foops_external['service_url'], foops_external['service_url'], code=True)}. "
                        if foops_external.get("service_url")
                        else ""
                    )
                    + (
                        f"Catalogue: {_href_html(foops_external['catalogue_url'], foops_external['catalogue_url'], code=True)}."
                        if foops_external.get("catalogue_url")
                        else ""
                    )
                ),
            }
        )
        for row in foops_external.get("dimension_scores", []):
            row_status = "watch" if row.get("score") is None else _status_for_ratio(float(row["score"]) / 100.0, 0.85, 0.7)
            value = "not assessed" if row.get("score") is None else f"{row['score']} / 100"
            external_fair_rows.append(
                {
                    "label": f"FOOPS! {row.get('acronym', row['dimension'][:1])} / {row['dimension']}",
                    "value": value,
                    "status": row_status,
                    "detail": "Returned directly by the FOOPS! service.",
                }
            )
    oops_rows: list[dict[str, str]] = []
    if oops_external.get("pitfall_count") is not None:
        oops_rows.append(
            {
                "label": "OOPS! pitfall count",
                "value": str(oops_external["pitfall_count"]),
                "status": _status_for_count(int(oops_external["pitfall_count"])),
                "detail": (
                    f"{oops_external.get('details', '')} "
                    + (
                        f"Service: {_href_html(oops_external['service_url'], oops_external['service_url'], code=True)}."
                        if oops_external.get("service_url")
                        else ""
                    )
                ),
            }
        )
        for level, count in sorted(oops_external.get("severity_counts", {}).items()):
            oops_rows.append(
                {
                    "label": f"OOPS! {level}",
                    "value": str(count),
                    "status": _status_for_count(int(count)),
                    "detail": "Pitfalls grouped by the importance level returned by OOPS!.",
                }
            )
    quality_signals = fair_dimension_signals + [
        {"label": "Source definition coverage", "value": f"{baseline_definition_coverage * 100:.1f}%", "status": _status_for_ratio(baseline_definition_coverage, 0.85, 0.6), "detail": "Coverage in the original mixed ontology before enrichment."},
        {"label": "Release missing definitions", "value": str(validation_report["missing_definition_count"]), "status": _status_for_count(int(validation_report["missing_definition_count"])), "detail": "Structural completeness after enrichment and validation."},
        {"label": "Generated annotations", "value": str(metadata_report.get("generated_annotations", 0)), "status": "watch" if metadata_report.get("generated_annotations", 0) else "good", "detail": "Generated annotations improve coverage but still require expert review."},
        {"label": "Hidden local file namespaces", "value": str(hidden_local_namespace_count), "status": "watch" if hidden_local_namespace_count else "good", "detail": "Local file-based namespaces are removed from the public namespace table."},
        {"label": "Placeholder-style definitions", "value": str(placeholder_definition_count), "status": "watch" if placeholder_definition_count else "good", "detail": "Generated definitions that still need editorial improvement."},
        {"label": "FOOPS! overall", "value": "not assessed" if foops_external.get("overall_score") is None else f"{foops_external['overall_score']} / 100", "status": "watch" if foops_external.get("overall_score") is None else _status_for_ratio(float(foops_external["overall_score"]) / 100.0, 0.85, 0.7), "detail": foops_external.get("details", "No FOOPS! result was recorded.")},
        {"label": "OOPS! pitfalls", "value": "not assessed" if oops_external.get("pitfall_count") is None else str(oops_external["pitfall_count"]), "status": "watch" if oops_external.get("pitfall_count") is None else _status_for_count(int(oops_external["pitfall_count"])), "detail": oops_external.get("details", "No OOPS! result was recorded.")},
        {"label": "OWL consistency hook", "value": validation_report["owl_consistency"]["status"], "status": "good" if validation_report["owl_consistency"]["status"] in {"loaded", "available"} else "watch", "detail": validation_report["owl_consistency"]["details"]},
        {"label": "w3id artifacts ready", "value": "Yes" if (root / "output" / "w3id" / ".htaccess").exists() else "No", "status": _status_for_flag((root / "output" / "w3id" / ".htaccess").exists()), "detail": "Redirect templates and content-negotiation notes are available."},
    ] + transparency_signals
    endpoint_rows = reference_iri_rows(namespace_policy, release_profile)
    metadata_rows = [
        {"label": "Title", "value": _graph_text(schema_graph, ontology_node, [DCTERMS.title]) or release_profile["project"]["title"]},
        {"label": "Ontology IRI", "value": namespace_policy["ontology_iri"]},
        {"label": "Version", "value": str(release_profile["release"]["version"])},
        {"label": "Namespace mode", "value": namespace_policy["namespace_mode"]},
        {"label": "License", "value": release_profile["release"]["ontology_license"], "href": release_profile["release"]["ontology_license"] if _is_web_url(release_profile["release"]["ontology_license"]) else ""},
        {"label": "Creators", "value": ", ".join(creators) or "Not recorded"},
        {"label": "Contributors", "value": ", ".join(contributors) or "Not recorded"},
    ]
    download_rows = [
        {"label": "Asserted source (Turtle)", "href": "source/ontology.ttl", "detail": "Immediate download of the asserted ontology module from the current publication tree."},
        {"label": "Asserted source (JSON-LD)", "href": "source/ontology.jsonld", "detail": "Machine-readable asserted release in JSON-LD."},
        {"label": "Inferred release", "href": "inferred/ontology.ttl", "detail": "Inferred schema and mapping export from the current publication tree."},
        {"label": "Latest asserted bundle", "href": "latest/ontology.ttl", "detail": "Stable latest-release alias inside the generated publication layout."},
        {"label": "JSON-LD context", "href": "context/context.jsonld", "detail": "JSON-LD context currently emitted by the release pipeline."},
        {"label": "Versioned release", "href": f"{release_profile['release']['version']}/ontology.ttl", "detail": "Version-pinned asserted ontology file in the publication tree."},
        {"label": "Versioned inferred", "href": f"{release_profile['release']['version']}/inferred.ttl", "detail": "Version-pinned inferred ontology file in the publication tree."},
    ]
    coverage_rows = [
        {"label": "Source label coverage", "value": f"{float(inspection_report['label_coverage']) * 100:.1f}%"},
        {"label": "Source definition coverage", "value": f"{baseline_definition_coverage * 100:.1f}%"},
        {"label": "Generated annotations", "value": str(metadata_report.get("generated_annotations", 0))},
        {"label": "Validation status", "value": validation_report["overall_status"]},
        {"label": "Resolver checks", "value": str(len(validation_report.get("resolver_checks", [])))},
    ]
    resource_rows = [
        {"label": "Reference page", "href": release_profile["publication"]["reference_page"], "value": "Single-page ontology reference"},
        {"label": "Release page", "href": "pages/release.html", "value": "Publication layout and release bundle overview"},
        {"label": "GitHub repository", "href": resources_cfg.get("repository_url", ""), "value": resources_cfg.get("repository_url", "")},
        {"label": "Pages URL", "href": resources_cfg.get("pages_url", ""), "value": resources_cfg.get("pages_url", "")},
        {"label": "OOPS!", "href": oops_external.get("service_url", ""), "value": oops_external.get("service_url", "")},
        {"label": "FOOPS!", "href": foops_external.get("service_url", ""), "value": foops_external.get("service_url", "")},
    ]

    index_template = env.get_template("index.html")
    write_text(
        output_dir / "index.html",
        index_template.render(
            page_title="Home",
            site=site,
            base_path=".",
            profile_heading=profile_heading,
            overview=overview,
            release_score=fair_scores["overall"],
            readiness_summary=f"{profile_label} is published as a conservative ontology release package with explicit separation of schema, curated vocabulary, and example or data-like content.",
            blockers=fair_scores["blockers"][:8] or ["No blocking issues detected."],
            cards=cards,
            highlights=highlights,
            featured_pages=featured_pages,
            quality_signals=quality_signals,
            namespace_rows=namespace_rows,
            use_cases=documentation_cfg.get("use_cases", []),
            audiences=documentation_cfg.get("audiences", []),
            resource_rows=resource_rows,
            reference_href=release_profile["publication"]["reference_page"],
            competency_preview=documentation_cfg.get("competency_questions", [])[:2],
            graph_poster=graph_poster,
            graph_poster_metrics=[
                {"label": "Schema", "value": str(len(classes) + len(properties))},
                {"label": "Vocabulary", "value": str(len(vocabulary_rows))},
                {"label": "Mapped", "value": str(mapping_stats["mapped"])},
                {"label": "Examples", "value": str(split_report.get("example_subject_count", 0))},
            ],
            module_cards=[
                {"title": "Schema module", "svg": _simple_svg_card("Schema module", "Local asserted classes and properties", str(len(classes) + len(properties)), "#ecfeff")},
                {"title": "Controlled vocabulary", "svg": _simple_svg_card("Controlled vocabulary", "Curated domain terms kept outside the schema", str(len(vocabulary_rows)), "#f0fdf4")},
                {"title": "Examples separated", "svg": _simple_svg_card("Examples separated", "Example and data-like resources in a separate module", str(split_report.get("example_subject_count", 0)), "#fff7ed")},
            ],
        ),
    )

    class_template = env.get_template("class_index.html")
    write_text(pages_dir / "class-index.html", class_template.render(page_title="Class Index", site=site, base_path="..", classes=classes))

    property_template = env.get_template("property_index.html")
    write_text(pages_dir / "property-index.html", property_template.render(page_title="Property Index", site=site, base_path="..", properties=properties))

    reference_template = env.get_template("reference.html")
    example_rows = collect_examples(examples_graph, classifications, limit=int(release_profile["release"]["docs_example_preview_limit"]))
    write_text(
        output_dir / release_profile["publication"]["reference_page"],
        reference_template.render(
            page_title="Ontology Reference",
            site=site,
            base_path=".",
            endpoint_rows=endpoint_rows,
            metadata_rows=metadata_rows,
            imports=imports,
            namespace_rows=namespace_rows,
            class_rows=classes,
            property_rows=properties,
            vocabulary_rows=vocabulary_rows,
            unit_review_rows=unit_review_rows,
            example_rows=example_rows,
            download_rows=download_rows,
            coverage_rows=coverage_rows,
            curation_note=f"The {profile_label} release guarantees structural completeness, but generated definitions and retained local vocabulary terms should still be curated by domain experts before claiming full conceptual maturity.",
            hmc_support={
                "logo_src": "assets/hmc-logo.svg",
                "hmc_url": hmc_url,
                "aimworks_url": aimworks_project_url,
                "text": "This ontology work is supported through the Helmholtz Metadata Collaboration (HMC) and the AIMWORKS project, connecting FAIR ontology publication to reusable metadata infrastructure.",
            },
        ),
    )

    examples_template = env.get_template("examples.html")
    write_text(
        pages_dir / "examples.html",
        examples_template.render(
            page_title="Examples",
            site=site,
            base_path="..",
            examples=example_rows,
            split_notes=split_report.get("notes", []),
        ),
    )

    alignment_template = env.get_template("alignment.html")
    local_keep_rows = [
        {
            "local_label": _clean_text(row.get("local_label", "")),
            "local_iri": row.get("local_iri", ""),
            "local_type": _clean_text(row.get("local_type", "")),
            "rationale": _clean_text(row.get("rationale", "No mapping rationale recorded.")),
        }
        for row in review_rows
        if not row.get("target_iri")
    ][:120]
    write_text(
        pages_dir / "alignment.html",
        alignment_template.render(
            page_title="Alignment",
            site=site,
            base_path="..",
            mappings=review_rows[:250],
            mapping_stats=mapping_stats,
            local_keep_rows=local_keep_rows,
        ),
    )

    release_template = env.get_template("release.html")
    release_files = [str(path.relative_to(root / "output")) for path in sorted((root / "output").rglob("*")) if path.is_file()]
    publication_rows = [
        {"label": "HTML reference page", "value": "ready" if (output_dir / release_profile["publication"]["reference_page"]).exists() else "missing", "status": _status_for_flag((output_dir / release_profile["publication"]["reference_page"]).exists())},
        {"label": "Machine-readable source", "value": "ready" if (root / "output" / "publication" / "source" / "ontology.ttl").exists() else "missing", "status": _status_for_flag((root / "output" / "publication" / "source" / "ontology.ttl").exists())},
        {"label": "Inferred serialization", "value": "ready" if (root / "output" / "publication" / "inferred" / "ontology.ttl").exists() else "missing", "status": _status_for_flag((root / "output" / "publication" / "inferred" / "ontology.ttl").exists())},
        {"label": "JSON-LD context", "value": "ready" if (root / "output" / "publication" / "context" / "context.jsonld").exists() else "missing", "status": _status_for_flag((root / "output" / "publication" / "context" / "context.jsonld").exists())},
        {"label": "Release bundle", "value": "ready" if (root / "output" / "release_bundle" / "manifest.json").exists() else "missing", "status": _status_for_flag((root / "output" / "release_bundle" / "manifest.json").exists())},
        {"label": "w3id artifacts", "value": "ready" if (root / "output" / "w3id" / ".htaccess").exists() else "missing", "status": _status_for_flag((root / "output" / "w3id" / ".htaccess").exists())},
    ]
    write_text(
        pages_dir / "release.html",
        release_template.render(
            page_title="Release",
            site=site,
            base_path="..",
            release_files=release_files[:140],
            fair_rows=fair_scores["dimensions"],
            transparency_rows=transparency_signals,
            external_fair_rows=external_fair_rows,
            oops_rows=oops_rows,
            validation_lines=[
                f"Overall status: {validation_report['overall_status']}",
                f"SHACL conforms: {validation_report['shacl_conforms']}",
                f"Missing labels: {validation_report['missing_label_count']}",
                f"Missing definitions: {validation_report['missing_definition_count']}",
            ],
            timeline_rows=documentation_cfg.get("release_story", []),
            endpoint_rows=endpoint_rows,
            publication_rows=publication_rows,
        ),
    )

    page_template = env.get_template("page.html")
    user_guide_html = """
<p>Run the pipeline from the <code>ontology_release</code> directory. The default release command performs inspection, split, alignment, enrichment, validation, documentation generation, w3id artifact generation, FAIR scoring, and release bundling.</p>
<pre><code>python -m aimworks_ontology_release.cli release --input input/current_ontology.jsonld</code></pre>
<p>For stepwise review:</p>
<ul>
  <li><code>inspect</code> writes ontology diagnostics and blockers.</li>
  <li><code>split</code> separates schema, vocabulary-like resources, and example/data-like content.</li>
  <li><code>map</code> generates conservative alignment proposals and a CSV review sheet.</li>
  <li><code>annotate</code> creates reviewable annotation drafts, with optional LLM support.</li>
  <li><code>validate</code> runs metadata, namespace, mapping, and SHACL checks.</li>
</ul>
<p>For deeper documentation, use the focused pages instead of scanning the full portal at once:</p>
<ul>
  <li><a href="scope-and-faq.html">Scope and FAQ</a> explains coverage boundaries and why modules are published separately.</li>
  <li><a href="modeling-patterns.html">Modeling Patterns</a> documents preferred patterns for measurements, materials, provenance, and publication.</li>
  <li><a href="import-guide.html">Import Guide</a> and <a href="import-catalog.html">Import Catalog</a> cover source ontologies, reuse targets, and release-time import strategy.</li>
  <li><a href="worked-examples.html">Worked Examples</a> provides JSON-LD, CSV-to-RDF, and notebook-style examples.</li>
  <li><a href="queries.html">Advanced SPARQL</a> keeps the browser query console available for power users without making it a top-level page for everyone.</li>
</ul>
"""
    write_text(
        pages_dir / "user-guide.html",
        page_template.render(
            page_title="Guide",
            site=site,
            base_path="..",
            heading="Guide",
            summary=f"Start here for the operational workflow, then branch into the deeper {profile_label} documentation only when you need it.",
            content_html=user_guide_html,
        ),
    )

    resource_html = (
        "<ul class='simple-list'>"
        + "".join(
            (
                f"<li><strong>{escape(row['label'])}</strong>: {_href_html(row['href'], row['value'])}</li>"
                if row.get("href")
                else f"<li><strong>{escape(row['label'])}</strong>: <code>{escape(_clean_text(row['value']))}</code></li>"
            )
            for row in [
                {"label": "Repository", "value": resources_cfg.get("repository_url", ""), "href": resources_cfg.get("repository_url", "")},
                {"label": "Issue tracker", "value": resources_cfg.get("issue_tracker", ""), "href": resources_cfg.get("issue_tracker", "")},
                {"label": "Pages URL", "value": resources_cfg.get("pages_url", ""), "href": resources_cfg.get("pages_url", "")},
                {"label": "Stable ontology IRI", "value": resources_cfg.get("ontology_homepage_iri", namespace_policy["ontology_iri"]), "href": ""},
                {"label": "OOPS!", "value": oops_external.get("service_url", ""), "href": oops_external.get("service_url", "")},
                {"label": "FOOPS!", "value": foops_external.get("service_url", ""), "href": foops_external.get("service_url", "")},
            ]
            if row["value"]
        )
        + "</ul>"
    )
    overview_html = (
        f"<p>{escape(overview['landing_intro'])}</p>"
        + "<h3>Core release facts</h3>"
        + "<ul class='simple-list'>"
        + f"<li>Ontology IRI: <code>{escape(namespace_policy['ontology_iri'])}</code></li>"
        + f"<li>Version: <code>{escape(str(release_profile['release']['version']))}</code></li>"
        + f"<li>Creators: {escape(', '.join(creators) or 'Not recorded')}</li>"
        + f"<li>Imports: {escape(', '.join(imports) or 'None declared in schema module')}</li>"
        + f"<li>License: <code>{escape(release_profile['release']['ontology_license'])}</code></li>"
        + f"<li>Namespace URI: <code>{escape(namespace_policy['preferred_namespace_uri'])}</code></li>"
        + "</ul>"
        + "<h3>Resource links</h3>"
        + resource_html
    )
    write_text(
        pages_dir / "ontology-overview.html",
        page_template.render(
            page_title="Ontology Overview",
            site=site,
            base_path="..",
            heading="Ontology Overview",
            summary=f"What the {profile_label} profile is, what it models, and which public release resources are available.",
            content_html=overview_html,
        ),
    )

    scope_html = (
        "<h3>In scope</h3>"
        + _list_html(documentation_cfg.get("scope", {}).get("in_scope", []))
        + "<h3>Out of scope</h3>"
        + _list_html(documentation_cfg.get("scope", {}).get("out_of_scope", []))
        + "<h3>Frequently asked questions</h3>"
        + _faq_html(documentation_cfg.get("faq", []))
    )
    write_text(
        pages_dir / "scope-and-faq.html",
        page_template.render(
            page_title="Scope and FAQ",
            site=site,
            base_path="..",
            heading="Scope and FAQ",
            summary=f"A concise explanation of {profile_label} scope, non-scope, and common release questions.",
            content_html=scope_html,
        ),
    )

    patterns_html = (
        f"<p>The patterns below are intended to keep the {profile_label} profile conservative, reviewable, and interoperable with the external ontologies it reuses.</p>"
        + _pattern_html(documentation_cfg.get("modeling_patterns", []))
    )
    write_text(
        pages_dir / "modeling-patterns.html",
        page_template.render(
            page_title="Modeling Patterns",
            site=site,
            base_path="..",
            heading="Modeling Patterns",
            summary=f"Recommended patterns for measurement, materials, process, provenance, and release publication in the {profile_label} profile.",
            content_html=patterns_html,
        ),
    )

    provenance_html = (
        f"<p>{platform_title} publishes both a source-oriented and a release-oriented provenance story. The release is intentionally conservative: it preserves profile-specific local concepts while documenting alignments, validation, and FAIR readiness.</p>"
        + _timeline_html(documentation_cfg.get("release_story", []))
    )
    write_text(
        pages_dir / "provenance-history.html",
        page_template.render(
            page_title="Provenance and History",
            site=site,
            base_path="..",
            heading="Provenance and History",
            summary=f"Release story, publication checkpoints, and why the {profile_label} profile uses a conservative ontology release process.",
            content_html=provenance_html,
        ),
    )

    governance_cfg = documentation_cfg.get("governance", {})
    governance_html = (
        "<h3>Editorial policy</h3>"
        + _list_html(governance_cfg.get("editorial_policy", []))
        + "<h3>Contribution path</h3>"
        + _list_html(governance_cfg.get("contribution_path", []))
        + "<h3>Versioning policy</h3>"
        + _list_html(governance_cfg.get("versioning_policy", []))
    )
    write_text(
        pages_dir / "governance.html",
        page_template.render(
            page_title="Governance",
            site=site,
            base_path="..",
            heading="Governance",
            summary=f"Editorial, contribution, and versioning guidance for {profile_label} ontology maintenance and release governance.",
            content_html=governance_html,
        ),
    )

    import_catalog_rows = import_catalog
    import_catalog_html = _html_table(
        ["Source", "Category", "Version", "Enabled", "Base IRI", "Fetch", "Source URL"],
        [
            [
                escape(_clean_text(row["title"])),
                escape(_clean_text(row["category"])),
                escape(_clean_text(row["version_label"])),
                escape(str(row["enabled"])),
                f"<code>{escape(_clean_text(row['base_iri']))}</code>",
                escape(_clean_text(row["fetch_kind"])),
                _href_html(row["fetch_location"], row["fetch_location"], code=True) if _is_web_url(row.get("fetch_location", "")) else f"<code>{escape(_clean_text(row.get('fetch_location', '')))}</code>",
            ]
            for row in import_catalog_rows
        ],
    )
    write_text(
        pages_dir / "import-catalog.html",
        page_template.render(
            page_title="Import Catalog",
            site=site,
            base_path="..",
            heading="Import Catalog",
            summary=f"Configured reuse targets and source ontologies for the active {profile_label} release profile.",
            content_html=(
                "<p>This catalog explains which external ontologies are configured as primary, fallback, or optional alignment sources for the release pipeline.</p>"
                + import_catalog_html
            ),
        ),
    )

    namespace_policy_html = (
        "<h3>Active release profile</h3>"
        + _list_html(
            [
                f"Active profile: {namespace_policy_raw['active_profile']}",
                f"Ontology IRI: {namespace_policy['ontology_iri']}",
                f"Term namespace: {namespace_policy['term_namespace']}",
                f"Namespace mode: {namespace_policy['namespace_mode']}",
                f"Preserve legacy IRIs: {namespace_policy['preserve_legacy_iris']}",
                f"Allow namespace migration: {namespace_policy['allow_namespace_migration']}",
            ]
        )
        + "<h3>Policy notes</h3>"
        + _list_html(documentation_cfg.get("namespace_policy_notes", []))
        + "<h3>Migration configuration</h3>"
        + _list_html(
            [
                f"Migration enabled: {namespace_policy_raw.get('migration', {}).get('enabled', False)}",
                f"New public base: {namespace_policy_raw.get('migration', {}).get('new_public_base', 'None')}",
                f"Alias map file: {namespace_policy_raw.get('migration', {}).get('alias_map_file', '')}",
            ]
        )
    )
    write_text(
        pages_dir / "namespace-policy.html",
        page_template.render(
            page_title="Namespace Policy",
            site=site,
            base_path="..",
            heading="Namespace Policy",
            summary=f"Stable IRI and namespace policy for the active {profile_label} publication profile.",
            content_html=namespace_policy_html,
        ),
    )

    deprecation_html = (
        f"<p>The {profile_label} profile treats deprecation as an explicit release-governed activity rather than a silent cleanup step.</p>"
        + _list_html(documentation_cfg.get("deprecation_policy", []))
    )
    write_text(
        pages_dir / "deprecation-policy.html",
        page_template.render(
            page_title="Deprecation Policy",
            site=site,
            base_path="..",
            heading="Deprecation Policy",
            summary="Rules for deprecating, replacing, and migrating ontology terms without silently breaking public identifiers.",
            content_html=deprecation_html,
        ),
    )

    citation_title = _clean_text(citation_meta.get("preferred-citation", {}).get("title") or citation_meta.get("title") or release_profile["project"]["title"])
    citation_version = _clean_text(citation_meta.get("preferred-citation", {}).get("version") or citation_meta.get("version") or release_profile["release"]["version"])
    doi_value = _clean_text(str(release_profile.get("citation", {}).get("doi") or zenodo_meta.get("doi") or "pending"))
    citation_badges = (
        f"<div class='chip-row'><span class='metric-pill'>Release {escape(citation_version)}</span>"
        f"<span class='metric-pill'>DOI {escape(doi_value)}</span>"
        f"<span class='metric-pill'>License {_href_html(release_profile['release']['ontology_license'], _clean_text(release_profile['release']['ontology_license'])) if _is_web_url(release_profile['release']['ontology_license']) else escape(_clean_text(release_profile['release']['ontology_license']))}</span>"
        f"<span class='metric-pill'>FAIR {escape(str(fair_scores['overall']))}</span></div>"
    )
    cite_html = (
        citation_badges
        + "<h3>Preferred ontology citation</h3>"
        + f"<p><strong>{escape(citation_title)}</strong>, version {escape(citation_version)}.</p>"
        + "<h3>How to cite</h3>"
        + _list_html(documentation_cfg.get("citation_guidance", []))
        + "<h3>Software package citation</h3>"
        + f"<p>{escape(_clean_text(citation_meta.get('title', f'{platform_title} release pipeline')))} ({escape(_clean_text(str(citation_meta.get('version', release_profile['release']['version']))))}).</p>"
    )
    write_text(
        pages_dir / "cite.html",
        page_template.render(
            page_title="How to Cite",
            site=site,
            base_path="..",
            heading="How to Cite",
            summary="Citation guidance for both the ontology release and the release-preparation software package.",
            content_html=cite_html,
        ),
    )

    import_snippet = f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/my-ontology> a owl:Ontology ;
  owl:imports <{namespace_policy['ontology_iri']}> .
"""
    rdflib_snippet = f"""from rdflib import Graph

graph = Graph()
graph.parse("{namespace_policy['ontology_iri']}/source", format="turtle")
"""
    import_html = (
        "<h3>Import guidance</h3>"
        + _list_html(documentation_cfg.get("import_guidance", []))
        + "<h3>OWL import example</h3>"
        + f"<pre><code>{escape(import_snippet)}</code></pre>"
        + "<h3>rdflib example</h3>"
        + f"<pre><code>{escape(rdflib_snippet)}</code></pre>"
        + "<h3>Stable release endpoints</h3>"
        + _html_table(
            ["Label", "IRI"],
            [[escape(row["label"]), f"<code>{escape(row['iri'])}</code>"] for row in endpoint_rows],
        )
    )
    write_text(
        pages_dir / "import-guide.html",
        page_template.render(
            page_title="How to Import",
            site=site,
            base_path="..",
            heading="How to Import",
            summary=f"Practical import and programmatic access guidance for the {profile_label} ontology release modules.",
            content_html=import_html,
        ),
    )

    jsonld_example = {
        "@context": {
            "h2kg": namespace_policy["preferred_namespace_uri"],
            "label": "http://www.w3.org/2000/01/rdf-schema#label",
            "usesInstrument": {"@id": f"{namespace_policy['term_namespace']}usesInstrument", "@type": "@id"},
            "hasOutputData": {"@id": f"{namespace_policy['term_namespace']}hasOutputData", "@type": "@id"},
        },
        "@id": "https://example.org/h2kg/demo/measurement-1",
        "@type": f"{namespace_policy['preferred_namespace_prefix']}:Measurement",
        "label": "Example ORR catalyst-layer measurement",
        "usesInstrument": "https://example.org/h2kg/demo/instrument-1",
        "hasOutputData": "https://example.org/h2kg/demo/data-1",
    }
    csv_example = "sample_id,instrument,current_density,unit\nrun-001,potentiostat-a,1.23,A-PER-CM2\n"
    csv_ttl_example = f"""@prefix ex: <https://example.org/h2kg/demo/> .
@prefix h2kg: <{namespace_policy['term_namespace']}> .

ex:run-001 a h2kg:Measurement ;
  h2kg:usesInstrument ex:potentiostat-a ;
  h2kg:hasOutputData ex:data-1 .
"""
    notebook_example = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [f"# {platform_title} release notebook starter\n", "Load the asserted schema and inspect a few mapped terms.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from rdflib import Graph\n",
                    "g = Graph()\n",
                    f"g.parse('{namespace_policy['ontology_iri']}/source', format='turtle')\n",
                    "len(g)\n",
                ],
            },
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    write_json(data_dir / "example_measurement.jsonld", jsonld_example)
    write_text(data_dir / "example_measurement.csv", csv_example)
    write_text(data_dir / "example_measurement.ttl", csv_ttl_example)
    write_json(data_dir / "example_release_notebook.ipynb", notebook_example)
    worked_examples_html = (
        f"<p>These researcher-facing examples show how the {profile_label} profile can be used in practical data and release workflows.</p>"
        + _list_html(documentation_cfg.get("researcher_extras", []))
        + "<h3>Downloadable examples</h3>"
        + _html_table(
            ["Artifact", "Path", "Purpose"],
            [
                ["JSON-LD measurement example", _href_html("../data/example_measurement.jsonld", "../data/example_measurement.jsonld", code=True), "Minimal measurement-oriented JSON-LD bundle."],
                ["CSV experiment example", _href_html("../data/example_measurement.csv", "../data/example_measurement.csv", code=True), "Small tabular experiment fragment."],
                ["CSV-to-RDF example", _href_html("../data/example_measurement.ttl", "../data/example_measurement.ttl", code=True), "RDF translation of the CSV fragment."],
                ["Notebook starter", _href_html("../data/example_release_notebook.ipynb", "../data/example_release_notebook.ipynb", code=True), "Programmatic inspection starter notebook."],
            ],
        )
    )
    write_text(
        pages_dir / "worked-examples.html",
        page_template.render(
            page_title="Worked Examples",
            site=site,
            base_path="..",
            heading="Worked Examples",
            summary=f"Researcher-facing JSON-LD, CSV-to-RDF, and notebook examples for {profile_label} release usage.",
            content_html=worked_examples_html,
        ),
    )

    changelog_entry = changelog_payload.get("entries", [{}])[0] if changelog_payload.get("entries") else {}
    changelog_html = (
        f"<p><strong>{escape(_clean_text(changelog_entry.get('version', 'current')))}</strong> ({escape(_clean_text(changelog_entry.get('date', '')))}): {escape(_clean_text(changelog_entry.get('summary', '')))}</p>"
        + "<h3>Changes</h3>"
        + _list_html(changelog_entry.get("changes", []))
        + "<h3>Notes</h3>"
        + _list_html(changelog_entry.get("notes", []))
    )
    write_text(
        pages_dir / "changelog.html",
        page_template.render(
            page_title="Changelog",
            site=site,
            base_path="..",
            heading="Changelog",
            summary=f"Release-oriented summary of what changed in the current {profile_label} publication baseline.",
            content_html=changelog_html,
        ),
    )

    quality_dashboard = {
        "fair_rows": [
            {"label": f"{row.get('acronym', row['dimension'][:1])} / {row['dimension']}", "value": f"{row['score']} / 100", "status": _status_for_ratio(float(row["score"]) / 100.0, 0.85, 0.7), "detail": f"Separated {row.get('acronym', row['dimension'][:1])} component of the release FAIR readiness score."}
            for row in fair_scores["dimensions"]
        ],
        "transparency_rows": transparency_signals,
        "external_fair_rows": external_fair_rows,
        "oops_rows": oops_rows,
        "validation_rows": [
            {"label": "Overall validation status", "value": validation_report["overall_status"], "status": "good" if validation_report["overall_status"] == "pass" else "watch", "detail": "Combined metadata, mapping, namespace, and SHACL status."},
            {"label": "SHACL conforms", "value": str(validation_report["shacl_conforms"]), "status": _status_for_flag(bool(validation_report["shacl_conforms"])), "detail": "Local release SHACL shapes."},
            {"label": "Missing labels", "value": str(validation_report["missing_label_count"]), "status": _status_for_count(int(validation_report["missing_label_count"])), "detail": "Release-time missing labels after enrichment."},
            {"label": "Missing definitions", "value": str(validation_report["missing_definition_count"]), "status": _status_for_count(int(validation_report["missing_definition_count"])), "detail": "Release-time missing definitions or comments after enrichment."},
            {"label": "Namespace violations", "value": str(len(validation_report["namespace_violations"])), "status": _status_for_count(len(validation_report["namespace_violations"])), "detail": "Violations against the active namespace policy."},
            {"label": "Mapping issues", "value": str(len(validation_report["mapping_issues"])), "status": _status_for_count(len(validation_report["mapping_issues"])), "detail": "Mappings that conflict with local term typing."},
            {"label": "OWL consistency hook", "value": validation_report["owl_consistency"]["status"], "status": "good" if validation_report["owl_consistency"]["status"] in {"loaded", "available"} else "watch", "detail": validation_report["owl_consistency"]["details"]},
            {"label": "EMMO checks", "value": validation_report["emmo_checks"]["status"], "status": "good" if validation_report["emmo_checks"]["status"] == "available" else "watch", "detail": validation_report["emmo_checks"]["details"]},
            {"label": "OOPS! hook", "value": validation_report["oops_checks"]["status"], "status": "good" if validation_report["oops_checks"]["status"] in {"reachable", "assessed"} else "watch", "detail": validation_report["oops_checks"]["details"]},
            {"label": "FOOPS! hook", "value": validation_report["foops_checks"]["status"], "status": "good" if validation_report["foops_checks"]["status"] in {"reachable", "assessed"} else "watch", "detail": validation_report["foops_checks"]["details"]},
        ],
        "hygiene_rows": [
            {"label": "Preferred prefix in public table", "value": namespace_policy["preferred_namespace_prefix"], "status": "good", "detail": "Public docs normalize the preferred namespace prefix for the local ontology."},
            {"label": "Placeholder-style definitions", "value": str(placeholder_definition_count), "status": "watch" if placeholder_definition_count else "good", "detail": "Generated definitions that still need expert editorial review."},
            {"label": "Imports declared in schema", "value": str(len(imports)), "status": "good" if imports else "watch", "detail": "Imported ontologies explicitly declared in the schema module."},
            {"label": "Baseline metadata gaps", "value": str(len(inspection_report.get('metadata_missing', []))), "status": "watch" if inspection_report.get("metadata_missing") else "good", "detail": "Source-ontology metadata gaps before enrichment."},
            {"label": "Configured import sources", "value": str(len(import_catalog_rows)), "status": "good" if import_catalog_rows else "watch", "detail": "Configured primary, fallback, and optional reuse targets for the release."},
        ],
        "publication_rows": publication_rows,
        "recommendations": [
            "Prioritize expert review of generated placeholder definitions before treating the release as a mature public vocabulary."
            if placeholder_definition_count
            else "Current structural validation is healthy; focus next on richer public examples and query support.",
            "Audit source content to remove local file-based namespace leakage before external publication."
            if hidden_local_namespace_count
            else "Public namespace hygiene is acceptable for release display.",
            "Review unmapped controlled vocabulary rows to decide which terms should remain local and which need better external alignment."
            if mapping_stats["unmapped"]
            else "Mapped and unmapped vocabulary balance looks stable for a conservative first release.",
        ],
    }

    dashboard_template = env.get_template("dashboard.html")
    write_text(
        pages_dir / "quality-dashboard.html",
        dashboard_template.render(
            page_title="Quality Dashboard",
            site=site,
            base_path="..",
            release_score=fair_scores["overall"],
            release_ready=fair_scores.get("release_ready", False),
            fair_rows=quality_dashboard["fair_rows"],
            transparency_rows=quality_dashboard["transparency_rows"],
            external_fair_rows=quality_dashboard["external_fair_rows"],
            oops_rows=quality_dashboard["oops_rows"],
            validation_rows=quality_dashboard["validation_rows"],
            hygiene_rows=quality_dashboard["hygiene_rows"],
            publication_rows=quality_dashboard["publication_rows"],
            recommendations=quality_dashboard["recommendations"],
        ),
    )

    query_sources = [
        {
            "id": "asserted",
            "label": "Asserted schema",
            "path": "../source/ontology.ttl",
            "fallback": "../../publication/source/ontology.ttl",
            "default": True,
        },
        {
            "id": "vocabulary",
            "label": "Controlled vocabulary",
            "path": "../source/controlled_vocabulary.ttl",
            "fallback": "../../publication/source/controlled_vocabulary.ttl",
            "default": True,
        },
        {
            "id": "alignments",
            "label": "Alignments",
            "path": "../source/alignments.ttl",
            "fallback": "../../publication/source/alignments.ttl",
            "default": True,
        },
        {
            "id": "examples",
            "label": "Examples",
            "path": "../examples/examples.ttl",
            "fallback": "../../publication/examples/examples.ttl",
            "default": False,
        },
        {
            "id": "inferred",
            "label": "Inferred ontology",
            "path": "../inferred/ontology.ttl",
            "fallback": "../../publication/inferred/ontology.ttl",
            "default": False,
        },
    ]
    queries_template = env.get_template("queries.html")
    write_text(
        pages_dir / "queries.html",
        queries_template.render(
            page_title="Advanced SPARQL",
            site=site,
            base_path="..",
            query_intro=_clean_text(documentation_cfg.get("query_guide", {}).get("introduction", "")),
            query_notes=documentation_cfg.get("query_guide", {}).get("notes", []),
            competency_questions=documentation_cfg.get("competency_questions", []),
            query_sources=query_sources,
            default_query=documentation_cfg.get("competency_questions", [{}])[0].get("sparql", ""),
        ),
    )

    explorer_module_rows = [
        {
            **query_sources[0],
            "id": "schema",
            "description": "Asserted local schema terms and ontology header metadata.",
            "graph": schema_graph,
        },
        {
            **query_sources[1],
            "id": "vocabulary",
            "description": "Curated named terms published outside the asserted schema module.",
            "graph": controlled_vocabulary_graph,
        },
        {
            **query_sources[2],
            "description": "Reviewed alignment assertions to external ontologies and vocabularies.",
            "graph": _load_optional_graph(root / "output" / "mappings" / "alignments.ttl"),
        },
        {
            **query_sources[3],
            "description": "Separated example and data-like content retained for demonstration and tutorials.",
            "graph": examples_graph,
        },
        {
            **query_sources[4],
            "description": "Optional inferred export generated by the release pipeline.",
            "graph": _load_optional_graph(root / "output" / "ontology" / "inferred.ttl"),
        },
    ]
    explorer_payload = _build_graph_explorer_payload(explorer_module_rows, namespace_policy, profile_label)
    explorer_payload = _enrich_explorer_nodes(explorer_payload, classes + properties + vocabulary_rows)

    visualizations_template = env.get_template("visualizations.html")
    visualization_rows = [
        {"title": "Ontology module overview", "body": "Release overview of asserted schema, controlled vocabulary, and separated example content.", "svg": _simple_svg_card("Schema/vocabulary split", "Release modularization overview", str(len(classes) + len(vocabulary_rows)), "#ecfeff")},
        {"title": "Import graph", "body": "Configured primary, fallback, and optional external ontologies for the active release profile.", "svg": _import_graph_svg(import_catalog_rows)},
        {"title": "Mapping coverage by source", "body": "External source ontologies currently contributing reviewed mappings.", "svg": _bar_chart_svg("Mapping coverage by source ontology", mapping_stats["sources"])},
        {"title": "Process, data, and provenance pattern", "body": "A publication-oriented modeling pattern for materials, measurements, outputs, and provenance.", "svg": _process_pattern_svg()},
        {"title": "Measurement neighborhood", "body": "Representative term neighborhood around a measurement-focused schema class.", "svg": _term_neighborhood_svg(classes, properties)},
        {"title": "Alignment relation mix", "body": "Reviewed relation types used across conservative mappings.", "svg": _bar_chart_svg("Alignment relation types", mapping_stats["relations"], "#d97706")},
    ]
    write_text(
        pages_dir / "visualizations.html",
        visualizations_template.render(
            page_title="Explore",
            site=site,
            base_path="..",
            explorer_data_path="../data/graph_explorer.json",
            explorer_overview=explorer_payload["overview"],
            explorer_modules=explorer_payload["modules"],
            visualizations=visualization_rows,
        ),
    )

    write_json(data_dir / "classes.json", classes)
    write_json(data_dir / "properties.json", properties)
    write_json(data_dir / "mappings.json", review_rows)
    write_json(data_dir / "reference_iris.json", endpoint_rows)
    write_json(data_dir / "quality_dashboard.json", quality_dashboard)
    write_json(data_dir / "query_examples.json", documentation_cfg.get("competency_questions", []))
    write_json(data_dir / "graph_explorer.json", explorer_payload)
    write_json(data_dir / "visualizations.json", [{"title": item["title"], "body": item["body"]} for item in visualization_rows])
    write_json(data_dir / "import_catalog.json", import_catalog_rows)
    write_json(data_dir / "local_keep_rows.json", local_keep_rows)
