"""工程 Agent：算量 / 报价 / 出图（MVP 简化，生产接真实 BOM 引擎）。

生产：每件构件绑定 BOM 模板 + 单价 + 出图规则，输出施工图 CAD/PDF。
"""


def calc_bom(scheme: dict) -> dict:
    bom = []
    for f in scheme["design"].get("furniture", []):
        bom.append({
            "name": f["cat"],
            "model": f.get("model"),
            "size": f["size"],
            "price": f.get("price", 0),
        })
    total = sum(b["price"] for b in bom)
    scheme["engineering"]["bom"] = bom
    scheme["engineering"]["quotation"] = {"total": total, "currency": "CNY"}
    return scheme


def export_pdf(scheme: dict, path: str = "delivery.pdf") -> str:
    """MVP 占位：真实接 CAD/PDF 生成库。"""
    return f"[MOCK] 交付包已导出至 {path}（含效果+尺寸+图纸+报价）"
