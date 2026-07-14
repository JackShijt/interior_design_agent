"""理解 Agent：户型识别（MVP 用 Mock + 清晰接口，生产接 CV 模型）。

生产接口签名保持一致，便于后续替换：
    recognize(image_path: str) -> dict  # 返回结构化 house 对象
"""
import json
import os

SCHEME_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scheme.json")


def recognize(image_path: str = None) -> dict:
    """MVP：直接返回内置示例户型（已结构化）。

    生产：调用 CV 模型（分割+检测+OCR+微分渲染）输出 house JSON。
    """
    with open(SCHEME_PATH, "r", encoding="utf-8") as f:
        scheme = json.load(f)
    house = scheme["house"]
    # 安全基线：记录初始墙体，供约束引擎检测"承重墙被移除"
    house["original_walls"] = [dict(w) for w in house["walls"]]
    return house


def apply_house(scheme: dict, house: dict) -> dict:
    scheme["house"] = house
    return scheme
