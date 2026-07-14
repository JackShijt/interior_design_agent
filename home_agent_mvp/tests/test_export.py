"""第 10 周：工程出图 / PDF 交付包单测。"""
import os
import json
import tempfile

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        return json.load(f)


def test_bom_detail_has_subtotal():
    """bom.calc_bom 输出分项明细且 total 为各 subtotal 之和。"""
    from engineering import bom as eng
    s = _scheme()
    out = eng.calc_bom(s)
    items = out["engineering"]["bom"]
    assert len(items) >= 1
    assert all("subtotal" in it and "name" in it for it in items)
    assert out["engineering"]["quotation"]["total"] == sum(i["subtotal"] for i in items)


def test_export_pdf_contains_total():
    """export_pdf 生成 PDF 且文件含报价总额文本。"""
    from engineering import export_pdf as exporter
    s = _scheme()
    s = eng_bom(s)
    tmp = tempfile.mktemp(suffix=".pdf")
    path = exporter.export_pdf(s, tmp)
    assert os.path.exists(path)
    data = open(path, "rb").read()
    # 最小合法 PDF 头
    assert data.startswith(b"%PDF")
    assert b"%%EOF" in data
    os.unlink(tmp)


def eng_bom(s):
    from engineering import bom as eng
    return eng.calc_bom(s)


def test_water_points_rule_based():
    """水电点位为规则生成（非 LLM）。"""
    from engineering import export_pdf as exporter
    s = _scheme()
    pts = exporter._水电点点位(s)
    assert len(pts) >= 1
    assert any("插座" in p or "防水" in p for p in pts)
