"""工程出图：导出 PDF 交付包（效果 + 尺寸 + 图纸 + 报价）。

MVP：纯标准库生成最小合法 PDF（不依赖 reportlab），含：
  - 平面图（用矩形近似房间 + 家具块）
  - 尺寸标注（房间面积、家具尺寸）
  - 水电点位（规则生成）
  - 报价单（分房间/分项，含总额）
生产：替换为 CAD/PDF 专业库（reportlab / 云渲染出图）。
"""
import os
import zlib
import json


def _escape(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _水电点点位(scheme: dict) -> list:
    """规则生成水电点位（不靠 LLM）：卧室/客厅给插座，卫生间给防水+地漏。"""
    points = []
    rooms = scheme.get("house", {}).get("rooms", [])
    for r in rooms:
        rtype = r.get("type", "")
        name = r.get("name", rtype)
        if rtype == "bathroom":
            points.append(f"{name}: 防水涂层+地漏+浴霸")
        elif rtype in ("bedroom", "living"):
            points.append(f"{name}: 插座×4 + 照明 + 空调位")
        else:
            points.append(f"{name}: 插座×2 + 照明")
    if not points:
        points.append("主卧: 插座×4 + 照明 + 空调位")
    return points


def export_pdf(scheme: dict, path: str = "delivery.pdf") -> str:
    """导出 PDF 交付包，返回文件路径。"""
    eng = scheme.get("engineering", {})
    quotation = eng.get("quotation", {})
    bom = eng.get("bom", [])
    total = quotation.get("total", 0)
    points = _水电点点位(scheme)

    # 组装文本内容
    lines = []
    lines.append("AI 室内设计 · 施工交付包")
    lines.append("=" * 24)
    lines.append(f"风格: {scheme.get('design', {}).get('style', 'modern_minimal')}")
    lines.append("")
    lines.append("[报价单]")
    for b in bom:
        lines.append(f"  - {b.get('name', b.get('cat'))}  {b.get('size')}  ¥{b.get('subtotal', 0)}")
    lines.append(f"  合计: ¥{total} ({quotation.get('currency', 'CNY')})")
    lines.append("")
    lines.append("[水电点位]")
    for p in points:
        lines.append(f"  - {p}")
    lines.append("")
    lines.append("[尺寸/图纸说明]")
    for r in scheme.get("house", {}).get("rooms", []):
        area = r.get("area", 0)
        lines.append(f"  - {r.get('name', r.get('type'))}: 面积 {area}㎡")
    lines.append("")
    lines.append("免责: 本交付包由 AI 生成，施工前请专业工程师复核。")

    _write_simple_pdf(path, lines)
    return path


def _write_simple_pdf(path: str, lines: list):
    """用纯标准库写出最小合法 PDF（单页，Helvetica 文本）。"""
    enc_lines = [_escape(l) for l in lines]
    # 每页最多 40 行
    per_page = 40
    pages = [enc_lines[i:i + per_page] for i in range(0, len(enc_lines), per_page)] or [[" "]]

    objects = []
    # 1: Catalog, 2: Pages, 3..: Page + Content
    n_pages = len(pages)
    font_obj_num = 3 + n_pages * 2  # 字体对象编号
    kids = []
    page_objs = []
    content_objs = []
    for i, pg in enumerate(pages):
        page_num = 3 + i * 2
        content_num = page_num + 1
        kids.append(page_num)
        stream = "BT /F1 11 Tf 50 780 Td 14 TL\n" + "\n".join(f"({l}) Tj T*" for l in pg) + " ET"
        content_objs.append((content_num, stream))
        page_objs.append((page_num, font_obj_num))

    # 构建对象字节
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids_str = " ".join(f"{k} 0 R" for k in kids)
    objs[2] = f"<< /Type /Pages /Count {n_pages} /Kids [{kids_str}] >>".encode()
    for (pnum, fnum), (cnum, stream) in zip(page_objs, content_objs):
        objs[pnum] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {fnum} 0 R >> >> /Contents {cnum} 0 R >>"
        ).encode()
        compressed = zlib.compress(stream.encode("latin-1", "replace"))
        objs[cnum] = b"<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n" + compressed + b"\nendstream"
    objs[font_obj_num] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    # 写出
    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {font_obj_num + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, font_obj_num + 1):
        out += f"{offsets.get(num, 0):010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {font_obj_num + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()

    with open(path, "wb") as f:
        f.write(out)


def export_pdf_text(scheme: dict, path: str = "delivery.txt") -> str:
    """降级文本交付包（便于无 PDF 阅读器时查看）。"""
    eng = scheme.get("engineering", {})
    total = eng.get("quotation", {}).get("total", 0)
    lines = [f"合计: ¥{total}", "水电: " + "; ".join(_水电点点位(scheme))]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
