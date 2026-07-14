"""生成 Agent（MVP 路线 A：可控构件拼装）。

真实系统：LLM 规划 Agent 输出空间策略 → 本模块按策略+约束从构件库拼装。
MVP：基于规则占位，保证可施工、可演示。
"""
import json
import os

COMPONENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "components.json")


def _load_components() -> dict:
    with open(COMPONENTS_PATH, "r", encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["components"]}


def generate(scheme: dict, user_need: str) -> dict:
    """依据需求文本，向 design.furniture 追加构件（MVP 占位逻辑）。"""
    comps = _load_components()
    need = (user_need or "").lower()

    # 多收纳 → 加衣柜；有床需求 → 加床；有客厅 → 加沙发
    additions = []
    if "收纳" in need or "衣柜" in need:
        additions.append(comps["wd_01"])
    if "床" in need or "卧室" in need or "两口" in need:
        additions.append(comps["bed_01"])
    if "沙发" in need or "客厅" in need:
        additions.append(comps["sofa_01"])

    # 默认至少给一个衣柜，保证首版非空
    if not additions:
        additions.append(comps["wd_01"])

    for c in additions:
        scheme["design"]["furniture"].append({
            "id": f"f_auto_{len(scheme['design']['furniture']) + 1}",
            "cat": c["cat"],
            "model": c["id"],
            "pos": [100, 100],
            "size": list(c["size"]),
            "price": c["price"],
        })

    # 风格推断（极简）
    if "简约" in need or "现代" in need:
        scheme["design"]["style"] = "modern_minimal"
    elif "暖" in need or "温馨" in need:
        scheme["design"]["style"] = "warm"

    return scheme
