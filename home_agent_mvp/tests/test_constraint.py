import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents import constraint

BASE = os.path.join(os.path.dirname(__file__), "..")
RULES = constraint.load_rules()


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        return json.load(f)


def test_load_rules():
    assert len(RULES) >= 5


def test_normal_scheme_passes():
    s = _scheme()
    s["house"]["original_walls"] = [dict(w) for w in s["house"]["walls"]]
    ok, report = constraint.evaluate(s, RULES)
    assert ok is True
    assert len(report["block"]) == 0


def test_remove_bearing_wall_blocked():
    s = _scheme()
    s["house"]["original_walls"] = [dict(w) for w in s["house"]["walls"]]
    # 模拟"拆除承重墙"请求：记录显式意图 + 从 walls 移除
    s.setdefault("pending_actions", []).append(
        {"action": "remove_wall", "wall_type": "bearing"}
    )
    s["house"]["walls"] = [w for w in s["house"]["walls"] if w["type"] != "bearing"]
    ok, report = constraint.evaluate(s, RULES)
    assert ok is False
    assert any("承重墙" in m for m in report["block"])
