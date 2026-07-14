"""第 7 周：全链路联调（mock 降级路径串起识别→规划→生成→对话→算量）。"""
import os
from agents import understand, planner, generator, dialog, constraint
from engineering import bom as eng


def _fresh_scheme():
    return {
        "project_id": "demo_001",
        "unit": "mm",
        "house": {},
        "design": {"style": "modern_minimal", "furniture": []},
        "engineering": {},
        "pending_actions": [],
    }


def test_full_pipeline_mock():
    # 1. 识别（mock）
    os.environ.pop("RECOGNITION_API_URL", None)
    scheme = _fresh_scheme()
    scheme["house"] = understand.recognize()
    assert scheme["house"].get("original_walls")

    # 2. 规划（mock）
    os.environ.pop("LLM_API_KEY", None)
    plan = planner.plan(scheme, "现代简约 两口之家 多收纳")
    assert plan["furniture_draft"]

    # 3. 生成
    scheme = generator.generate(scheme, "现代简约 两口之家 多收纳")
    assert len(scheme["design"]["furniture"]) >= 1

    # 4. 约束校验（必经）
    rules = constraint.load_rules()
    ok, report = constraint.evaluate(scheme, rules)
    assert ok is True

    # 5. 算量
    scheme = eng.calc_bom(scheme)
    assert scheme["engineering"]["quotation"]["total"] > 0

    # 6. 对话修改（mock 正则：加长衣柜 30cm）
    before = [f for f in scheme["design"]["furniture"] if f["cat"] == "wardrobe"][0]["size"][0]
    scheme, msg = dialog.dialog_with_mock(scheme, "主卧衣柜加长 30cm")
    after = [f for f in scheme["design"]["furniture"] if f["cat"] == "wardrobe"][0]["size"][0]
    assert after == before + 300

    # 7. 对话后再次约束+算量
    ok2, _ = constraint.evaluate(scheme, rules)
    assert ok2 is True
    scheme = eng.calc_bom(scheme)
    assert scheme["engineering"]["quotation"]["total"] > 0
