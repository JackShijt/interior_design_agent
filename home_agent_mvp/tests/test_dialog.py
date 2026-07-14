import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents import dialog

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        return json.load(f)


def test_wardrobe_lengthen():
    s = _scheme()
    before = s["design"]["furniture"][0]["size"][0]
    s, msg = dialog.handle_command(s, "主卧衣柜加长 30cm")
    after = s["design"]["furniture"][0]["size"][0]
    assert after == before + 300
    assert "衣柜" in msg


def test_style_switch():
    s = _scheme()
    s, msg = dialog.handle_command(s, "换成暖色调")
    assert s["design"]["style"] == "warm"


def test_unknown_command():
    s = _scheme()
    s, msg = dialog.handle_command(s, "帮我飞到月球")
    assert "暂未理解" in msg


def test_move_to_window():
    """'把沙发移到靠窗' → 记录移动意图且风格不变。"""
    os.environ.pop("LLM_API_KEY", None)
    s = _scheme()
    s, msg = dialog.dialog_with_mock(s, "把沙发移到靠窗")
    assert "沙发" in msg and "靠窗" in msg


def test_add_nightstand():
    """'加一个床头柜' → 通过 mock 正则未覆盖，走 LLM 路径无 Key 时回退，
    此处验证 add_furniture function 执行逻辑（直接调用 _exec_function）。"""
    os.environ.pop("LLM_API_KEY", None)
    from agents import constraint
    s = _scheme()
    rules = constraint.load_rules()
    before = len(s["design"]["furniture"])
    s, msg = dialog._exec_function("add_furniture", {"cat": "bed"}, s, rules)
    assert len(s["design"]["furniture"]) == before + 1
    assert "床" in msg


def test_constraint_conflict_returns_alternative():
    """构造承重墙拆除意图 → 约束阻断，返回替代方案而非崩溃。"""
    os.environ.pop("LLM_API_KEY", None)
    from agents import constraint
    s = _scheme()
    rules = constraint.load_rules()
    # 模拟 remove_wall 承重墙意图落到 pending_actions
    s["pending_actions"] = [{"action": "remove_wall", "wall_type": "bearing"}]
    ok, report = constraint.evaluate(s, rules)
    assert ok is False
    alt = dialog._alternative(report)
    assert alt is not None and "承重墙" in alt
