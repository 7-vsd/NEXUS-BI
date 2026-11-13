"""Power BI static validation, DAG structure and Streamlit smoke tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not (ROOT / "powerbi" / "model_schema.json").exists()
                    or not (ROOT / "data" / "processed" / "powerbi" / "fact_orders.csv").exists(),
                    reason="needs powerbi/build_pbip.py output and the database-produced CSV extracts")
def test_powerbi_static_validation_passes():
    from powerbi.validate_pbip import run
    res = run()
    assert all(r["status"] == "PASS" for r in res), [r for r in res if r["status"] != "PASS"]


def test_dax_library_has_required_functions_and_30_plus_measures():
    from powerbi.dax.measures import MEASURES
    assert len(MEASURES) >= 30
    text = " ".join(m[1] for m in MEASURES)
    for fn in ["CALCULATE", "FILTER", "SUMX", "AVERAGEX", "RANKX", "ALL (", "ALLEXCEPT", "SAMEPERIODLASTYEAR",
               "DATEADD", "TOTALYTD", "USERELATIONSHIP", "SWITCH"]:
        assert fn in text, fn
    assert len({m[0] for m in MEASURES}) == len(MEASURES)          # unique names


def test_rls_roles_defined():
    roles = list((ROOT / "powerbi" / "NexusBI.SemanticModel" / "definition" / "roles").glob("*.tmdl"))
    assert len(roles) >= 6
    assert any("USERPRINCIPALNAME" in r.read_text() for r in roles)


def test_dag_task_chain_without_airflow():
    """Airflow-independent check of the declared chain (full DagBag test is in the testing report)."""
    src = (ROOT / "orchestration" / "dags" / "nexus_bi_pipeline.py").read_text()
    for t in ["EXTRACT", "VALIDATE", "TRANSFORM", "LOAD_DATABASE", "RUN_ANALYTICS", "GENERATE_PREDICTIONS", "PUBLISH_OUTPUTS"]:
        assert f'"{t}"' in src
    assert "ONE_FAILED" in src and '"retries": 2' in src


@pytest.mark.skipif(importlib.util.find_spec("airflow") is None, reason="Airflow not installed in this environment")
def test_dag_parses_in_airflow():
    from airflow.models import DagBag
    db = DagBag(dag_folder=str(ROOT / "orchestration" / "dags"), include_examples=False)
    assert not db.import_errors
    assert len(db.get_dag("nexus_bi_pipeline").tasks) == 9


PAGES = sorted((ROOT / "app" / "pages").glob("*.py"))


@pytest.mark.skipif(not (ROOT / "data" / "processed" / "order_mart.parquet").exists(), reason="run the pipeline first")
@pytest.mark.parametrize("page", [p.name for p in PAGES])
def test_streamlit_page_renders_without_exception(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=240)
    at.run()
    if page != PAGES[0].name:
        at.switch_page(f"pages/{page}")
        at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_report_accessibility_metadata():
    """Every visual has non-empty English alt text and a unique, reading-order tab order (WCAG 2.1 / EN 301 549)."""
    pages = ROOT / "powerbi" / "NexusBI.Report" / "definition" / "pages"
    for page in [p for p in pages.iterdir() if p.is_dir()]:
        visuals = [json.loads(f.read_text(encoding="utf-8")) for f in page.glob("visuals/*/visual.json")]
        orders = []
        for v in visuals:
            alt = v["visual"]["visualContainerObjects"]["general"][0]["properties"]["altText"]["expr"]["Literal"]["Value"]
            assert len(alt.strip("'")) > 10, (page.name, v["name"])
            assert " che " not in alt and "Grafico" not in alt, f"non-English alt text: {alt}"
            orders.append(v["position"]["tabOrder"])
        assert len(set(orders)) == len(orders) and all(t % 1000 == 0 and t > 0 for t in orders), page.name
        from powerbi.build_pbip import reading_order
        expected = [v["position"]["tabOrder"] for v in reading_order(visuals)]
        assert expected == sorted(expected, reverse=True), page.name   # reading order gets descending tab order
        for f in page.glob("visuals/*/visual.json"):
            assert not f.read_bytes().startswith(b"\xef\xbb\xbf"), f"BOM in {f}"
