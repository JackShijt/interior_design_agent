"""生成 Agent（MVP 路线 A：可控构件拼装）。

真实系统：LLM 规划 Agent 输出空间策略 → 本模块按策略+约束从构件库拼装。
MVP：基于规则占位，按需求关键词 + 风格标签从构件库选取，保证可施工、可演示。
"""
import json
import os

COMPONENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "components.json")


def _load_components() -> dict:
    with open(COMPONENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["components"]


# 需求关键词 → 构件类别
_NEED_TO_CAT = [
    ("收纳", "wardrobe"), ("衣柜", "wardrobe"), ("衣帽间", "wardrobe"),
    ("床", "bed"), ("卧室", "bed"), ("两口", "bed"), ("主卧", "bed"),
    ("沙发", "sofa"), ("客厅", "sofa"),
    ("书桌", "desk"), ("办公", "desk"), ("学习", "desk"),
    ("餐桌", "table"), ("吃饭", "table"), ("茶几", "table"),
    ("床头柜", "nightstand"),
    ("电视柜", "tv_cabinet"),
    ("餐边柜", "cabinet"), ("书柜", "cabinet"), ("储物", "cabinet"),
    ("橱柜", "kitchen"), ("厨房", "kitchen"),
    ("浴室柜", "bath_cabinet"), ("卫浴", "bath_cabinet"), ("卫生间", "bath_cabinet"),
    ("置物架", "shelf"), ("飘窗", "shelf"),
    ("鞋柜", "shoe_cabinet"), ("玄关", "shoe_cabinet"),
    ("餐椅", "chair"), ("椅子", "chair"),
]

_STYLE_LABEL = {"modern_minimal": "现代简约", "warm": "温馨"}


def _pick(comps, cat, style):
    """按类别+风格标签选取一件构件；无风格匹配则取该类第一件。"""
    cand = [c for c in comps if c["cat"] == cat]
    if not cand:
        return None
    styled = [c for c in cand if style in c.get("style_tags", [])]
    return (styled or cand)[0]


def generate(scheme: dict, user_need: str) -> dict:
    """依据需求文本，向 design.furniture 追加构件（按风格筛选）。"""
    comps = _load_components()
    need = (user_need or "").lower()

    # 风格推断
    style = "modern_minimal"
    if "暖" in need or "温馨" in need:
        style = "warm"
    scheme["design"]["style"] = style

    # 收集需求涉及的类别（去重，保持出现顺序）
    wanted = []
    for kw, cat in _NEED_TO_CAT:
        if kw in need and cat not in wanted:
            wanted.append(cat)

    # 默认至少给一个衣柜，保证首版非空
    if not wanted:
        wanted.append("wardrobe")

    furniture = scheme["design"].get("furniture", [])
    # 简单网格布局，避免重叠：每件沿 x 轴错开 50px
    x_cursor = 100
    for cat in wanted:
        c = _pick(comps, cat, style)
        if c is None:
            continue
        furniture.append({
            "id": f"f_auto_{len(furniture) + 1}",
            "cat": c["cat"],
            "model": c["id"],
            "pos": [x_cursor, 100],
            "size": list(c["size"]),
            "price": c["price"],
        })
        x_cursor += c["size"][0] + 50

    scheme["design"]["furniture"] = furniture
    return scheme
