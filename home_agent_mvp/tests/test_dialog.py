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
