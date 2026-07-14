"""第 2 周：bom + constraint + dialog 单测。"""
import os

from engineering import bom as eng
from agents import constraint, dialog


def test_bom_is_material_list_without_price():
    """bom.calc_bom 产出材料/工程量清单，且不含任何费用字段（quotation/subtotal/unit_price）。"""
    scheme = {
        "design": {"style": "modern_minimal", "furniture": [
            {"cat": "wardrobe", "model": "wd_01", "size": [1800, 600, 2400]},
            {"cat": "bed", "model": "bed_01", "size": [1800, 2000, 450]},
        ]},
        "engineering": {},
    }
    out = eng.calc_bom(scheme)
    bom = out["engineering"]["bom"]
    assert len(bom) == 2
    # 无报价
    assert "quotation" not in out["engineering"]
    for b in bom:
        assert "items" in b and len(b["items"]) >= 1
        assert "subtotal" not in b and "unit_price" not in b
        for it in b["items"]:
            assert "qty" in it and "unit" in it
            assert "subtotal" not in it and "unit_price" not in it


def test_bom_wardrobe_has_banjin_and_wujin_items():
    """衣柜 wd_01 应拆出「板材(㎡)」与「五金(套)」两项分项（含工程量，无价）。"""
    scheme = {
        "design": {"style": "modern_minimal", "furniture": [
            {"cat": "wardrobe", "model": "wd_01", "size": [1800, 600, 2400]},
        ]},
        "engineering": {},
    }
    out = eng.calc_bom(scheme)
    b = out["engineering"]["bom"][0]
    item_names = [i["name"] for i in b["items"]]
    assert "板材" in item_names and "五金" in item_names
    # 板材工程量 = 宽×深 = 1.8×0.6 = 1.08 ㎡
    banjin = next(i for i in b["items"] if i["name"] == "板材")
    assert banjin["unit"] == "㎡"
    assert banjin["qty"] == round(1.8 * 0.6, 3)


def test_bom_kitchen_uses_linear_meter():
    """橱柜 kitchen_01 的柜体/台面应为延米(m)，工程量=宽/1000。"""
    scheme = {
        "design": {"style": "modern_minimal", "furniture": [
            {"cat": "kitchen", "model": "kitchen_01", "size": [3000, 600, 900]},
        ]},
        "engineering": {},
    }
    out = eng.calc_bom(scheme)
    b = out["engineering"]["bom"][0]
    linear = [i for i in b["items"] if i["unit"] in ("m", "延米", "米")]
    assert len(linear) == 2  # 柜体 + 台面
    assert linear[0]["qty"] == 3.0  # 3000mm → 3m


def test_constraint_wardrobe_depth_500_optimize():
    """constraint.evaluate 对'衣柜深度 500'（越界）应产生 optimize 提示。"""
    rules = constraint.load_rules()
    scheme = {
        "design": {"style": "modern_minimal", "furniture": [
            # 深度 500 不在建议区间 [550, 600]
            {"cat": "wardrobe", "model": "wd_01", "size": [1800, 500, 2400], "price": 3200},
        ]},
        "house": {"walls": [], "original_walls": [], "rooms": []},
        "pending_actions": [],
    }
    passed, report = constraint.evaluate(scheme, rules)
    assert passed is True  # optimize 不阻断
    assert any("衣柜深度" in m for m in report["optimize"])


def test_dialog_switch_to_warm():
    """dialog.handle_command 对'换成暖色调'应把 style 改为 warm。"""
    os.environ.pop("LLM_API_KEY", None)
    scheme = {
        "design": {"style": "modern_minimal", "furniture": []},
        "house": {"walls": [], "original_walls": []},
        "pending_actions": [],
    }
    out, msg, ctx = dialog.handle_command(scheme, "换成暖色调")
    assert out["design"]["style"] == "warm"
    assert "warm" in msg
