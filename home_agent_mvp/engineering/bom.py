"""工程算量：构件 → 材料/工程量清单（不含费用）。

聚焦「材料与工程量」，用于施工备料与施工图标注，不做报价。
算量规则（基于构件 bom_template 用量公式）：
- 板材/层板/岩板/台面 类面材：工程量 = 长(m) × 深(m)（或宽×深），单位 ㎡；
- 柜体/台面延米（以「m」为单位）：工程量 = 宽(mm) / 1000；
- 五金/椅架/床架/沙发/镜柜/台盆 等「套/件」类：工程量 = 件数 × 1。
分项 = {name, unit, qty}；构件 = {name, model, cat, size, items[]}。
"""
import os
import json


def _load_components() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "components.json")
    with open(path, "r", encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["components"]}


# 工程量单位分类
_AREA_UNITS = {"㎡", "m2", "平方米"}
_LINEAR_UNITS = {"m", "米", "延米"}


def _quantity_for(bom_item: dict, comp: dict, size: list) -> float:
    """根据 bom_template 的 unit 计算单项工程量。"""
    unit = bom_item.get("unit", "套")
    w, d, h = size[0], size[1], size[2] if len(size) > 2 else 0
    if unit in _AREA_UNITS:
        # 板材/层板/岩板/台面：投影面积 ≈ 宽 × 深（mm→m）
        return round(w / 1000 * d / 1000, 3)
    if unit in _LINEAR_UNITS:
        # 橱柜柜体/台面延米：按宽
        return round(w / 1000, 3)
    # 套 / 件 类（五金、椅架、床架、沙发、台盆、镜柜…）：按件
    return 1.0


def calc_bom(scheme: dict) -> dict:
    """把设计家具展开为材料/工程量清单，写入 engineering.bom（无费用字段）。"""
    comps = _load_components()
    bom = []
    for f in scheme["design"].get("furniture", []):
        model = f.get("model")
        comp = comps.get(model, {})
        name = comp.get("name", f["cat"])
        size = f["size"]

        items = []
        for tpl in comp.get("bom_template", []):
            qty = _quantity_for(tpl, comp, size)
            items.append({
                "name": tpl.get("name"),
                "unit": tpl.get("unit"),
                "qty": qty,
                "material": tpl.get("material") or (comp.get("materials", [None]) or [None])[0],
            })

        bom.append({
            "name": name,
            "model": model,
            "cat": f["cat"],
            "size": size,
            "qty": 1,
            "items": items,
        })

    scheme.setdefault("engineering", {})["bom"] = bom
    # 移除报价：只保留材料清单
    scheme["engineering"].pop("quotation", None)
    return scheme


if __name__ == "__main__":
    s = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "scheme.json"), encoding="utf-8"))
    out = calc_bom(s)
    for b in out["engineering"]["bom"]:
        print(b["name"], b["items"])
