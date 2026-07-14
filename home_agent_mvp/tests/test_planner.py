"""第 3 周：planner 单测（无 Key 走 mock，有 Key 走真实调用）。"""
import os
from agents import planner


def test_plan_mock_without_key():
    """无 LLM_API_KEY 时走 mock，返回合理结构。"""
    os.environ.pop("LLM_API_KEY", None)
    scheme = {"design": {"furniture": []}}
    out = planner.plan(scheme, "现代简约 两口之家 多收纳")
    assert "furniture_draft" in out
    assert any(f["cat"] == "wardrobe" for f in out["furniture_draft"])
    assert out["style"] == "modern_minimal"


def test_plan_mock_keywords():
    """关键词映射正确：客厅→sofa。"""
    os.environ.pop("LLM_API_KEY", None)
    scheme = {"design": {"furniture": []}}
    out = planner.plan(scheme, "需要客厅 沙发")
    assert any(f["cat"] == "sofa" for f in out["furniture_draft"])


def test_plan_with_mock_explicit():
    """显式调用降级函数结构完整。"""
    out = planner.plan_with_mock({}, "多收纳")
    assert "rooms" in out and "style" in out
