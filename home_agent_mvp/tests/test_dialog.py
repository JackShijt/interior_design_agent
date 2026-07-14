import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents import dialog

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        s = json.load(f)
    # 确保有一件衣柜供尺寸类用例使用（不依赖磁盘运行态数据）
    if not s["design"].get("furniture"):
        s["design"]["furniture"] = [
            {"id": "f1", "cat": "wardrobe", "model": "wd_01",
             "pos": [100, 100], "size": [1800, 600, 2400]},
        ]
    return s


def test_wardrobe_lengthen():
    s = _scheme()
    before = s["design"]["furniture"][0]["size"][0]
    s, msg, ctx = dialog.handle_command(s, "主卧衣柜加长 30cm")
    after = s["design"]["furniture"][0]["size"][0]
    assert after == before + 300
    assert "衣柜" in msg
    assert ctx.get("last_cat") == "wardrobe"  # 上下文记录


def test_context_reference_increase():
    """上下文指代：'再大点' 沿用上一轮的衣柜/宽度维度。"""
    os.environ.pop("LLM_API_KEY", None)
    s = _scheme()
    ctx = {}
    s, msg1, ctx = dialog.dialog_with_mock(s, "主卧衣柜加长 30cm", ctx)
    w_before = s["design"]["furniture"][0]["size"][0]
    s, msg2, ctx = dialog.dialog_with_mock(s, "再大点", ctx)
    w_after = s["design"]["furniture"][0]["size"][0]
    assert w_after == w_before + 100  # 默认 +100mm 指代


def test_style_switch():
    s = _scheme()
    s, msg, ctx = dialog.handle_command(s, "换成暖色调")
    assert s["design"]["style"] == "warm"


def test_style_toggle_by_reference():
    """'换个风格' 在 modern_minimal / warm 间切换（依赖上下文）。"""
    os.environ.pop("LLM_API_KEY", None)
    s = _scheme()
    ctx = {"last_style": "modern_minimal"}
    s, msg, ctx = dialog.dialog_with_mock(s, "换个风格", ctx)
    assert s["design"]["style"] == "warm"


def test_unknown_command():
    s = _scheme()
    s, msg, ctx = dialog.handle_command(s, "帮我飞到月球")
    assert "暂未理解" in msg


def test_move_to_window():
    """'把沙发移到靠窗' → 记录移动意图且风格不变。"""
    os.environ.pop("LLM_API_KEY", None)
    s = _scheme()
    s, msg, ctx = dialog.dialog_with_mock(s, "把沙发移到靠窗")
    assert "沙发" in msg and "靠窗" in msg


def test_add_desk_full_category():
    """全品类覆盖：'加一组书桌' 应能新增 desk 品类。"""
    os.environ.pop("LLM_API_KEY", None)
    s = _scheme()
    before = len(s["design"]["furniture"])
    s, msg, ctx = dialog.dialog_with_mock(s, "加一组书桌", {})
    cats = [f["cat"] for f in s["design"]["furniture"]]
    assert "desk" in cats
    assert len(s["design"]["furniture"]) == before + 1


def test_constraint_conflict_returns_alternative():
    """构造承重墙拆除意图 → 约束阻断，返回替代方案而非崩溃。"""
    os.environ.pop("LLM_API_KEY", None)
    from agents import constraint
    s = _scheme()
    rules = constraint.load_rules()
    s["pending_actions"] = [{"action": "remove_wall", "wall_type": "bearing"}]
    ok, report = constraint.evaluate(s, rules)
    assert ok is False
    alt = dialog._alternative(report)
    assert alt is not None and "承重墙" in alt
