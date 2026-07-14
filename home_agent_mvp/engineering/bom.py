"""工程 Agent：算量 / 报价 / 出图（MVP 简化，生产接真实 BOM 引擎）。

生产：每件构件绑定 BOM 模板 + 单价 + 出图规则，输出施工图 CAD/PDF。
"""
import os
import json


def _load_components() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "components.json")
    with open(path, "r", encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["components"]}


def calc_bom(scheme: dict) -> dict:
    comps = _load_components()
    bom = []
    for f in scheme["design"].get("furniture", []):
        model = f.get("model")
        comp = comps.get(model, {})
        name = comp.get("name", f["cat"])
        unit_price = f.get("price", comp.get("price", 0))
        bom.append({
            "name": name,
            "model": model,
            "cat": f["cat"],
            "size": f["size"],
            "bom_template": comp.get("bom_template", []),
            "unit_price": unit_price,
            "qty": 1,
            "subtotal": unit_price,
        })
    total = sum(b["subtotal"] for b in bom)
    scheme["engineering"]["bom"] = bom
    scheme["engineering"]["quotation"] = {"total": total, "currency": "CNY"}
    return scheme


def export_pdf(scheme: dict, path: str = "delivery.pdf") -> str:
    """MVP 占位：真实接 CAD/PDF 生成库。"""
    return f"[MOCK] 交付包已导出至 {path}（含效果+尺寸+图纸+报价）"
