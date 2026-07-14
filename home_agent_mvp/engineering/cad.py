"""CAD 施工图纸生成：scheme → DXF（AutoCAD 可打开）+ SVG 在线预览。

设计目标：输出一套「施工级」室内平面布置图，可直接在 AutoCAD/浩辰/中望 打开。
遵循室内施工图基本规范：
  - 分图层（墙体 / 门窗 / 家具 / 轴线 / 尺寸 / 文字 / 图框 / 水电点位），各层配色；
  - 墙体双线（按 thickness），门窗断开 + 门扇弧线示意；
  - 尺寸标注（房间净尺寸 / 总尺寸）；
  - 水电点位（插座/照明/地漏/防水）规则生成并布点；
  - A3 图框 + 标题栏（项目 / 比例 / 图号 / 日期 / 设计）。

依赖：优先 ezdxf 生成 .dxf；未安装时自动降级为 .svg（浏览器可直接预览）。
单位：绘图坐标沿用 scheme 的 mm；标注文字按毫米。
"""
import os
import math
import datetime

try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    _HAS_EZDXF = True
except Exception:
    _HAS_EZDXF = False


# ---------------------------------------------------------------------------
# 图层定义（名称, AutoCAD 颜色索引 ACI）
# ---------------------------------------------------------------------------
LAYERS = {
    "WALL":    {"color": 7,  "desc": "墙体"},
    "WALL_BEARING": {"color": 1, "desc": "承重墙"},
    "DOOR":    {"color": 3,  "desc": "门窗"},
    "FURN":    {"color": 5,  "desc": "家具"},
    "DIM":     {"color": 2,  "desc": "尺寸标注"},
    "TEXT":    {"color": 7,  "desc": "文字"},
    "MEP":     {"color": 6,  "desc": "水电点位"},
    "FRAME":   {"color": 8,  "desc": "图框"},
    "AXIS":    {"color": 4,  "desc": "轴线"},
}


# ---------------------------------------------------------------------------
# 水电点位（规则生成，与 export_pdf 一致的施工语义）
# ---------------------------------------------------------------------------
def mep_points(scheme: dict) -> list:
    """按房间类型规则生成水电点位坐标 + 说明。返回 [{pos:[x,y], label, kind}]。"""
    pts = []
    for r in scheme.get("house", {}).get("rooms", []):
        poly = r.get("poly", [])
        if not poly:
            continue
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        rtype = r.get("type", "")
        name = r.get("name", rtype)
        if rtype == "bathroom":
            pts.append({"pos": [cx, cy], "label": f"{name} 地漏", "kind": "drain"})
            pts.append({"pos": [cx + 400, cy], "label": "防水/浴霸", "kind": "power"})
        elif rtype in ("bedroom", "living"):
            # 沿墙布 4 个插座 + 1 照明
            for i, (dx, dy) in enumerate([(-800, -800), (800, -800), (800, 800), (-800, 800)]):
                pts.append({"pos": [cx + dx, cy + dy], "label": "插座", "kind": "socket"})
            pts.append({"pos": [cx, cy], "label": f"{name} 照明", "kind": "light"})
        elif rtype == "kitchen":
            pts.append({"pos": [cx, cy], "label": f"{name} 照明", "kind": "light"})
            pts.append({"pos": [cx + 600, cy], "label": "厨房强电", "kind": "power"})
        else:
            pts.append({"pos": [cx, cy], "label": f"{name} 照明", "kind": "light"})
            pts.append({"pos": [cx + 500, cy], "label": "插座", "kind": "socket"})
    return pts


def _bbox(scheme: dict):
    """图元包围盒 (minx, miny, maxx, maxy)。"""
    xs, ys = [], []
    for w in scheme.get("house", {}).get("walls", []):
        for p in (w.get("p1"), w.get("p2")):
            if p:
                xs.append(p[0]); ys.append(p[1])
    if not xs:
        return (0, 0, 5000, 4000)
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# DXF 生成（ezdxf）
# ---------------------------------------------------------------------------
def _wall_segments(w: dict):
    """返回墙中心线两端点。"""
    return w["p1"], w["p2"]


def _perp(p1, p2, dist):
    """求线段 p1->p2 的单位法向 × dist。"""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ln = math.hypot(dx, dy) or 1
    return (-dy / ln * dist, dx / ln * dist)


def export_dxf(scheme: dict, path: str) -> str:
    """生成施工级平面布置图 DXF。返回文件路径。"""
    doc = ezdxf.new(setup=True)
    doc.units = 4  # mm
    msp = doc.modelspace()

    for name, cfg in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=cfg["color"])

    house = scheme.get("house", {})
    design = scheme.get("design", {})

    # —— 墙体：中心线偏移出双线 ——
    for w in house.get("walls", []):
        p1, p2 = _wall_segments(w)
        t = w.get("thickness", 200)
        layer = "WALL_BEARING" if w.get("type") in ("bearing", "suspect_load_bearing") else "WALL"
        ox, oy = _perp(p1, p2, t / 2)
        a1 = (p1[0] + ox, p1[1] + oy); a2 = (p2[0] + ox, p2[1] + oy)
        b1 = (p1[0] - ox, p1[1] - oy); b2 = (p2[0] - ox, p2[1] - oy)
        msp.add_line(a1, a2, dxfattribs={"layer": layer})
        msp.add_line(b1, b2, dxfattribs={"layer": layer})
        # 端封口
        msp.add_line(a1, b1, dxfattribs={"layer": layer})
        msp.add_line(a2, b2, dxfattribs={"layer": layer})

    # —— 门窗：在墙上断开示意 + 门扇弧线 ——
    for op in house.get("openings", []):
        w = next((x for x in house.get("walls", []) if x.get("id") == op.get("wall_id")), None)
        if not w:
            continue
        p1, p2 = _wall_segments(w)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx / ln, dy / ln
        off = op.get("offset", 0)
        width = op.get("width", 900)
        s = (p1[0] + ux * off, p1[1] + uy * off)
        e = (p1[0] + ux * (off + width), p1[1] + uy * (off + width))
        if op.get("type") == "door":
            # 门扇：一条边 + 90° 开启弧
            msp.add_line(s, (s[0] - uy * width, s[1] + ux * width), dxfattribs={"layer": "DOOR"})
            start_ang = math.degrees(math.atan2(uy, ux))
            msp.add_arc(center=s, radius=width, start_angle=start_ang,
                        end_angle=start_ang + 90, dxfattribs={"layer": "DOOR"})
        else:
            # 窗：双线
            msp.add_line(s, e, dxfattribs={"layer": "DOOR"})

    # —— 房间名 + 面积 ——
    for r in house.get("rooms", []):
        poly = r.get("poly", [])
        if not poly:
            continue
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        label = f"{r.get('name', r.get('type', '房间'))}\n{r.get('area', '')}m2"
        msp.add_text(label, dxfattribs={"layer": "TEXT", "height": 180}).set_placement(
            (cx, cy + 300), align=TextEntityAlignment.MIDDLE_CENTER)

    # —— 家具：矩形 + 类别文字 ——
    cat_label = {"wardrobe": "衣柜", "bed": "床", "sofa": "沙发", "desk": "书桌",
                 "table": "餐桌", "chair": "椅", "cabinet": "柜", "kitchen": "橱柜",
                 "nightstand": "床头柜", "tv_cabinet": "电视柜", "bath_cabinet": "浴室柜",
                 "shelf": "置物架", "shoe_cabinet": "鞋柜"}
    for f in design.get("furniture", []):
        px, py = f.get("pos", [0, 0])
        w0, d0 = f["size"][0], f["size"][1]
        pts = [(px, py), (px + w0, py), (px + w0, py + d0), (px, py + d0), (px, py)]
        msp.add_lwpolyline(pts, dxfattribs={"layer": "FURN"})
        msp.add_text(cat_label.get(f.get("cat"), f.get("cat", "")),
                     dxfattribs={"layer": "FURN", "height": 120}).set_placement(
            (px + w0 / 2, py + d0 / 2), align=TextEntityAlignment.MIDDLE_CENTER)

    # —— 水电点位 ——
    mep_sym = {"socket": "○插", "light": "⊗灯", "drain": "◇漏", "power": "▣电"}
    for pt in mep_points(scheme):
        x, y = pt["pos"]
        msp.add_circle((x, y), radius=80, dxfattribs={"layer": "MEP"})
        msp.add_text(mep_sym.get(pt["kind"], "○"),
                     dxfattribs={"layer": "MEP", "height": 100}).set_placement(
            (x, y - 200), align=TextEntityAlignment.MIDDLE_CENTER)

    # —— 尺寸标注：整体总尺寸（下 + 左）——
    minx, miny, maxx, maxy = _bbox(scheme)
    dim_off = 700
    dim = msp.add_linear_dim(
        base=(minx, miny - dim_off), p1=(minx, miny), p2=(maxx, miny),
        dxfattribs={"layer": "DIM"})
    dim.render()
    dim2 = msp.add_linear_dim(
        base=(minx - dim_off, miny), p1=(minx, miny), p2=(minx, maxy),
        angle=90, dxfattribs={"layer": "DIM"})
    dim2.render()

    # —— A3 图框 + 标题栏 ——
    _draw_frame_dxf(msp, scheme, (minx, miny, maxx, maxy))

    doc.saveas(path)
    return path


def _draw_frame_dxf(msp, scheme, bbox):
    """在图形外围绘制图框 + 标题栏（随图形范围自适应放大）。"""
    minx, miny, maxx, maxy = bbox
    pad = 1200
    x0, y0 = minx - pad, miny - pad - 900
    x1, y1 = maxx + pad, maxy + pad
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
                       dxfattribs={"layer": "FRAME"})
    # 标题栏（右下角）
    tb_w, tb_h = min(3200, (x1 - x0) * 0.5), 800
    tx0, ty0 = x1 - tb_w, y0
    msp.add_lwpolyline([(tx0, ty0), (x1, ty0), (x1, ty0 + tb_h), (tx0, ty0 + tb_h), (tx0, ty0)],
                       dxfattribs={"layer": "FRAME"})
    today = datetime.date.today().isoformat()
    style = scheme.get("design", {}).get("style", "modern_minimal")
    lines = [
        f"项目: {scheme.get('project_id', 'demo')}  平面布置图",
        f"风格: {style}   比例: 1:100",
        f"图号: JS-01   日期: {today}   设计: AI 室内设计",
    ]
    for i, ln in enumerate(lines):
        msp.add_text(ln, dxfattribs={"layer": "TEXT", "height": 160}).set_placement(
            (tx0 + 150, ty0 + tb_h - 220 - i * 240), align=TextEntityAlignment.LEFT)


# ---------------------------------------------------------------------------
# SVG 生成（无 ezdxf 时降级，浏览器可直接预览）
# ---------------------------------------------------------------------------
def export_svg(scheme: dict, path: str) -> str:
    """生成 SVG 平面布置图（在线预览用）。返回文件路径。"""
    svg = build_svg(scheme)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path


def build_svg(scheme: dict) -> str:
    """构建 SVG 字符串（Y 轴翻转为屏幕坐标，含图框/墙/门/家具/房间/水电/标注）。"""
    house = scheme.get("house", {})
    design = scheme.get("design", {})
    minx, miny, maxx, maxy = _bbox(scheme)
    pad = 1400
    W = (maxx - minx) + pad * 2
    H = (maxy - miny) + pad * 2 + 1000  # 底部留标题栏
    # 世界坐标 → SVG（平移 + Y 翻转）
    def X(x): return x - minx + pad
    def Y(y): return (maxy - y) + pad  # 翻转

    el = []
    el.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
              f'font-family="PingFang SC, Microsoft YaHei, sans-serif">')
    el.append(f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" fill="#ffffff"/>')

    # 图框
    fx, fy = pad * 0.4, pad * 0.4
    el.append(f'<rect x="{fx:.0f}" y="{fy:.0f}" width="{W - fx*2:.0f}" height="{H - fy*2:.0f}" '
              f'fill="none" stroke="#333" stroke-width="6"/>')

    # 房间地面填充 + 名称
    palette = ["#f5f7fb", "#f3f6f0", "#faf5ef", "#f0f4f8"]
    for i, r in enumerate(house.get("rooms", [])):
        poly = r.get("poly", [])
        if len(poly) < 3:
            continue
        pts = " ".join(f"{X(p[0]):.0f},{Y(p[1]):.0f}" for p in poly)
        el.append(f'<polygon points="{pts}" fill="{palette[i % len(palette)]}" stroke="#c9d2e0" stroke-width="2"/>')
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        el.append(f'<text x="{X(cx):.0f}" y="{Y(cy):.0f}" font-size="200" fill="#222" '
                  f'text-anchor="middle">{r.get("name", "房间")}</text>')
        el.append(f'<text x="{X(cx):.0f}" y="{Y(cy)-260:.0f}" font-size="150" fill="#667" '
                  f'text-anchor="middle">{r.get("area", "")} m²</text>')

    # 墙体（双线）
    for w in house.get("walls", []):
        p1, p2 = w["p1"], w["p2"]
        t = w.get("thickness", 200)
        bearing = w.get("type") in ("bearing", "suspect_load_bearing")
        color = "#d23c4e" if bearing else "#333"
        ox, oy = _perp(p1, p2, t / 2)
        for s, e in (((p1[0]+ox, p1[1]+oy), (p2[0]+ox, p2[1]+oy)),
                     ((p1[0]-ox, p1[1]-oy), (p2[0]-ox, p2[1]-oy))):
            el.append(f'<line x1="{X(s[0]):.0f}" y1="{Y(s[1]):.0f}" x2="{X(e[0]):.0f}" y2="{Y(e[1]):.0f}" '
                      f'stroke="{color}" stroke-width="{max(4, t/25):.0f}"/>')

    # 门窗
    for op in house.get("openings", []):
        w = next((x for x in house.get("walls", []) if x.get("id") == op.get("wall_id")), None)
        if not w:
            continue
        p1, p2 = w["p1"], w["p2"]
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx/ln, dy/ln
        off = op.get("offset", 0); wid = op.get("width", 900)
        s = (p1[0]+ux*off, p1[1]+uy*off)
        e = (p1[0]+ux*(off+wid), p1[1]+uy*(off+wid))
        el.append(f'<line x1="{X(s[0]):.0f}" y1="{Y(s[1]):.0f}" x2="{X(e[0]):.0f}" y2="{Y(e[1]):.0f}" '
                  f'stroke="#3fb27f" stroke-width="10"/>')
        if op.get("type") == "door":
            # 开启弧
            ex, ey = s[0]-uy*wid, s[1]+ux*wid
            el.append(f'<path d="M {X(s[0]):.0f} {Y(s[1]):.0f} A {wid:.0f} {wid:.0f} 0 0 1 '
                      f'{X(ex):.0f} {Y(ey):.0f}" fill="none" stroke="#3fb27f" stroke-width="3" stroke-dasharray="12,10"/>')

    # 家具
    cat_label = {"wardrobe": "衣柜", "bed": "床", "sofa": "沙发", "desk": "书桌",
                 "table": "餐桌", "chair": "椅", "cabinet": "柜", "kitchen": "橱柜",
                 "nightstand": "床头柜", "tv_cabinet": "电视柜", "bath_cabinet": "浴室柜",
                 "shelf": "置物架", "shoe_cabinet": "鞋柜"}
    for f in design.get("furniture", []):
        px, py = f.get("pos", [0, 0])
        w0, d0 = f["size"][0], f["size"][1]
        rx, ry = X(px), Y(py + d0)  # 左上角（翻转后）
        el.append(f'<rect x="{rx:.0f}" y="{ry:.0f}" width="{w0:.0f}" height="{d0:.0f}" '
                  f'fill="#e8eefc" stroke="#4a6bff" stroke-width="3"/>')
        el.append(f'<text x="{X(px+w0/2):.0f}" y="{Y(py+d0/2):.0f}" font-size="140" fill="#3552c9" '
                  f'text-anchor="middle">{cat_label.get(f.get("cat"), f.get("cat",""))}</text>')

    # 水电点位
    kind_color = {"socket": "#e67e22", "light": "#f1c40f", "drain": "#3498db", "power": "#9b59b6"}
    kind_sym = {"socket": "插", "light": "灯", "drain": "漏", "power": "电"}
    for pt in mep_points(scheme):
        x, y = pt["pos"]
        c = kind_color.get(pt["kind"], "#888")
        el.append(f'<circle cx="{X(x):.0f}" cy="{Y(y):.0f}" r="90" fill="#fff" stroke="{c}" stroke-width="4"/>')
        el.append(f'<text x="{X(x):.0f}" y="{Y(y)+45:.0f}" font-size="110" fill="{c}" '
                  f'text-anchor="middle">{kind_sym.get(pt["kind"], "·")}</text>')

    # 总尺寸标注（下沿）
    dy0 = Y(miny) + 500
    el.append(f'<line x1="{X(minx):.0f}" y1="{dy0:.0f}" x2="{X(maxx):.0f}" y2="{dy0:.0f}" stroke="#f39c12" stroke-width="3"/>')
    for xx in (minx, maxx):
        el.append(f'<line x1="{X(xx):.0f}" y1="{Y(miny):.0f}" x2="{X(xx):.0f}" y2="{dy0+40:.0f}" stroke="#f39c12" stroke-width="2"/>')
    el.append(f'<text x="{X((minx+maxx)/2):.0f}" y="{dy0-40:.0f}" font-size="160" fill="#c87f0a" '
              f'text-anchor="middle">{int(maxx-minx)} mm</text>')

    # 标题栏
    today = datetime.date.today().isoformat()
    style = design.get("style", "modern_minimal")
    tb_y = H - fy - 620
    el.append(f'<rect x="{W-fx-3400:.0f}" y="{tb_y:.0f}" width="3400" height="560" fill="#fafbfd" stroke="#333" stroke-width="4"/>')
    tb_lines = [
        f"{scheme.get('project_id','demo')}  ·  平面布置图",
        f"风格: {style}    比例: 1:100",
        f"图号: JS-01   日期: {today}",
        "设计: AI 室内设计（施工前请工程师复核）",
    ]
    for i, ln in enumerate(tb_lines):
        el.append(f'<text x="{W-fx-3250:.0f}" y="{tb_y+150+i*130:.0f}" font-size="120" fill="#333">{_esc(ln)}</text>')

    el.append('</svg>')
    return "\n".join(el)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def export_cad(scheme: dict, out_dir: str) -> dict:
    """生成施工图：优先 DXF（AutoCAD），并始终生成 SVG（浏览器预览）。

    返回 {"dxf": path|None, "svg": path, "format": "dxf"|"svg"}。
    """
    os.makedirs(out_dir, exist_ok=True)
    svg_path = os.path.join(out_dir, "construction_plan.svg")
    export_svg(scheme, svg_path)
    result = {"dxf": None, "svg": svg_path, "format": "svg"}
    if _HAS_EZDXF:
        try:
            dxf_path = os.path.join(out_dir, "construction_plan.dxf")
            export_dxf(scheme, dxf_path)
            result["dxf"] = dxf_path
            result["format"] = "dxf"
        except Exception as e:
            result["dxf_error"] = str(e)
    return result


if __name__ == "__main__":
    import json
    base = os.path.join(os.path.dirname(__file__), "..")
    s = json.load(open(os.path.join(base, "data", "scheme.json"), encoding="utf-8"))
    out = export_cad(s, os.path.join(base, "data", "cad"))
    print("CAD 生成:", out)
