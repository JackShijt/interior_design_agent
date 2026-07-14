"""第 2 周：bom + constraint + dialog 单测。"""
from engineering import bom as eng
from agents import constraint, dialog


def test_bom_total_is_sum_of_prices():
    """bom.calc_bom 计算 total = 各家具 price 之和。"""
    scheme = {
        "design": {"style": "modern_minimal", "furniture": [
            {"cat": "wardrobe", "model": "wd_01", "size": [1800, 600, 2400], "price": 3200},
            {"cat": "bed", "model": "bed_01", "size": [1800, 2000, 450], "price": 2600},
        ]},
        "engineering": {},
    }
    out = eng.calc_bom(scheme)
    assert out["engineering"]["quotation"]["total"] == 3200 + 2600
    assert len(out["engineering"]["bom"]) == 2


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
    scheme = {
        "design": {"style": "modern_minimal", "furniture": []},
        "house": {"walls": [], "original_walls": []},
        "pending_actions": [],
    }
    out, msg = dialog.handle_command(scheme, "换成暖色调")
    assert out["design"]["style"] == "warm"
    assert "warm" in msg
