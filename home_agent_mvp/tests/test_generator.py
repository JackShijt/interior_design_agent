"""第 2 周：generator 单测。"""
from agents import generator


def _empty_scheme():
    return {
        "design": {"style": "modern_minimal", "furniture": []},
        "house": {"walls": [], "original_walls": []},
        "pending_actions": [],
    }


def test_generate_multistorage_appends_wardrobe():
    """对'多收纳'需求能追加 wardrobe。"""
    scheme = _empty_scheme()
    out = generator.generate(scheme, "现代简约 两口之家 多收纳")
    cats = [f["cat"] for f in out["design"]["furniture"]]
    assert "wardrobe" in cats


def test_generate_empty_need_appends_at_least_one():
    """对空需求至少追加 1 件家具。"""
    scheme = _empty_scheme()
    out = generator.generate(scheme, "")
    assert len(out["design"]["furniture"]) >= 1


def test_generate_sofa_for_living():
    """客厅需求追加 sofa。"""
    scheme = _empty_scheme()
    out = generator.generate(scheme, "需要客厅 沙发")
    cats = [f["cat"] for f in out["design"]["furniture"]]
    assert "sofa" in cats
