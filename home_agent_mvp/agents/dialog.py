"""对话 Agent（MVP：正则解析；生产：LLM Function Calling）。

把自然语言修改映射为对 scheme JSON 的结构化编辑。
支持指令示例：
  - "主卧衣柜加长 30cm"
  - "衣柜加宽 20cm"
  - "换成暖色调"
返回 (scheme, message)。冲突/越界走约束引擎拦截。
"""
import re


def _price_for(cat: str, size: list) -> int:
    """MVP 简化计价：按宽度线性。生产接构件库 BOM。"""
    base = {"wardrobe": 3200, "bed": 2600, "sofa": 3500}.get(cat, 1000)
    return int(base + size[0] * 1.0)


def handle_command(scheme: dict, text: str):
    text = text or ""
    changed = False
    msgs = []

    # 类别关键词 → cat 字段
    cat_keywords = {
        "衣柜": "wardrobe", "柜": "wardrobe",
        "床": "bed", "沙发": "sofa",
    }
    # 维度关键词 → size 索引
    dim_map = {"长": 0, "宽": 1, "高": 2, "深": 1, "深": 1}

    # 尺寸修改：检测 <类别词> + 加? <维度词> + <数字> cm
    target_cat = None
    for kw, cat in cat_keywords.items():
        if kw in text:
            target_cat = cat
            break

    cat_label = {"wardrobe": "衣柜", "bed": "床", "sofa": "沙发"}
    num_m = re.search(r"(\d+)\s*cm", text)
    dim_m = re.search(r"加?\s*(长|宽|高|深)", text)
    if target_cat and num_m and dim_m:
        idx = dim_map[dim_m.group(1)]
        delta = int(num_m.group(1)) * 10  # cm -> mm
        for f in scheme["design"]["furniture"]:
            if f["cat"] == target_cat:
                f["size"][idx] += delta
                f["price"] = _price_for(f["cat"], f["size"])
                changed = True
                msgs.append(f"{cat_label.get(f['cat'], f['cat'])} {dim_m.group(1)} 调整为 {f['size'][idx]}mm")
                break

    # 风格切换
    if not changed:
        if "暖" in text or "温馨" in text:
            scheme["design"]["style"] = "warm"
            changed = True
            msgs.append("风格切换为 warm")
        elif "现代" in text or "简约" in text:
            scheme["design"]["style"] = "modern_minimal"
            changed = True
            msgs.append("风格切换为 modern_minimal")

    if not changed:
        return scheme, "暂未理解该指令（MVP 仅支持尺寸修改/风格切换示例）。"

    return scheme, "；".join(msgs)
