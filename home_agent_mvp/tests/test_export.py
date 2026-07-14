"""施工图（CAD/SVG）生成单测 —— 取代旧的 PDF 报价交付包。"""
import os
import json
import tempfile

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        return json.load(f)


def test_bom_is_material_list():
    """bom.calc_bom 输出材料清单，且无报价字段。"""
    from engineering import bom as eng
    s = _scheme()
    out = eng.calc_bom(s)
    assert "bom" in out["engineering"]
    assert "quotation" not in out["engineering"]


def test_export_svg_is_valid():
    """export_cad 始终生成 SVG，内容为合法 svg。"""
    from engineering import cad
    s = _scheme()
    tmp = tempfile.mkdtemp()
    out = cad.export_cad(s, tmp)
    assert os.path.exists(out["svg"])
    data = open(out["svg"], encoding="utf-8").read()
    assert data.lstrip().startswith("<svg")
    assert "</svg>" in data


def test_export_dxf_when_ezdxf_available():
    """若安装了 ezdxf，则生成合法 DXF（AutoCAD 可打开）。"""
    from engineering import cad
    if not cad._HAS_EZDXF:
        import pytest
        pytest.skip("ezdxf 未安装，走 SVG 降级")
    s = _scheme()
    tmp = tempfile.mkdtemp()
    out = cad.export_cad(s, tmp)
    assert out["format"] == "dxf"
    assert out["dxf"] and os.path.exists(out["dxf"])
    head = open(out["dxf"], "rb").read(64)
    # DXF 文件以 SECTION 段开头
    assert b"SECTION" in open(out["dxf"], "rb").read(2000)


def test_mep_points_rule_based():
    """水电点位为规则生成（非 LLM），含坐标与说明。"""
    from engineering import cad
    s = _scheme()
    pts = cad.mep_points(s)
    assert len(pts) >= 1
    assert all("pos" in p and "label" in p and "kind" in p for p in pts)
