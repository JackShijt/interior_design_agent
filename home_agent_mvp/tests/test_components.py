"""第 6 周：构件库 + generator 拼装单测。"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
COMPONENTS_PATH = os.path.join(BASE, "data", "components.json")

from agents import generator


def _load_comps():
    with open(COMPONENTS_PATH, encoding="utf-8") as f:
        return json.load(f)["components"]


def test_components_count_over_30():
    """构件库 ≥ 30 件。"""
    comps = _load_comps()
    assert len(comps) >= 30


def test_each_component_has_price_and_bom():
    """每件含 unit_price 与 bom_template。"""
    for c in _load_comps():
        assert "price" in c and isinstance(c["price"], (int, float))
        assert c["price"] > 0
        assert "bom_template" in c and len(c["bom_template"]) > 0


def test_generator_multi_category_no_overlap():
    """对综合需求能拼出 ≥3 件且不重叠（pos x 递增）。"""
    scheme = {"design": {"style": "modern_minimal", "furniture": []},
              "house": {"walls": [], "original_walls": []}, "pending_actions": []}
    out = generator.generate(scheme, "现代简约 两口之家 多收纳 需要书桌 餐桌 沙发")
    cats = [f["cat"] for f in out["design"]["furniture"]]
    assert len(cats) >= 3
    # 不重叠：相邻家具 x 区间不相交
    xs = [(f["pos"][0], f["pos"][0] + f["size"][0]) for f in out["design"]["furniture"]]
    for i in range(len(xs) - 1):
        assert xs[i][1] <= xs[i + 1][0], f"重叠: {xs[i]} vs {xs[i+1]}"
