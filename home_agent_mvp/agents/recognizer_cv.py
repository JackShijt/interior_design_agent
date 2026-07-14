"""真实户型识别引擎（纯本地 OpenCV，无需训练/GPU）。

适用输入：白底黑线的 CAD 线稿 / 户型截图类图像（横平竖直的正交户型）。
对拍照类（畸变/家具/阴影）效果有限，靠「前端手动校正」兜底（见 understand + 前端校正视图）。

识别流程：
  1. 读图 → 灰度 → 自适应二值化（墙线为前景）
  2. 形态学闭运算连接断线、去噪
  3. 标准霍夫直线 → 一组 (rho, theta) 直线
  4. 直线聚类（角度量化到 0/90° 附近）→ 去重
  5. 每条直线沿墙像素采样 + 与他线交点 → 截断成干净墙段
  6. flood-fill 区域分割 → 房间多边形（含面积）
  7. 门洞：共线墙段间缺口启发式 → openings
  8. 比例校准：tesseract OCR 读尺寸标注 + 像素 → mm/px；无标注回退启发式

对外主函数：recognize_cv(image_path) -> dict
"""
import re
import math
import subprocess
import numpy as np
import cv2


# --------------------------------------------------------------------------- #
# 1. 图像二值化
# --------------------------------------------------------------------------- #
def _load_binary(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图像: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 加白边：避免墙线贴图像边缘时自适应阈值（窗口越界）把墙线当噪声抑制
    gray = cv2.copyMakeBorder(gray, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    bin_raw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 8
    )
    # 闭运算版：连接断线，供墙线提取（但会抹平门洞，门洞检测另用 bin_raw）
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    bin_closed = cv2.morphologyEx(bin_raw, cv2.MORPH_CLOSE, k, iterations=2)
    bin_closed = cv2.morphologyEx(bin_closed, cv2.MORPH_OPEN, k, iterations=1)
    return bin_closed, bin_raw, gray


# --------------------------------------------------------------------------- #
# 2. 标准霍夫直线 + 聚类
# --------------------------------------------------------------------------- #
def _hough_lines(bin_inv, threshold=40):
    """返回 (rho, theta) 直线列表。theta∈[0,π)。"""
    out = cv2.HoughLines(bin_inv, 1, np.pi / 180, threshold)
    if out is None:
        return []
    lines = [(float(r[0][0]), float(r[0][1])) for r in out]
    return _cluster_lines(lines)


def _cluster_lines(lines, theta_tol=0.18, rho_tol=14):
    """按方向量化到 0(水平) 或 π/2(垂直) 聚类去重，返回代表 (rho, theta)。

    用 round(theta/(π/2))%2 区分水平/垂直，避免把横竖墙混为一类。
    """
    reps = []  # [rho, base_theta, count]
    for rho, theta in lines:
        k = round(theta / (math.pi / 2))
        base = (k % 2) * (math.pi / 2)
        if abs(theta - base) > math.pi / 4:
            continue  # 过斜，正交户型忽略
        # 把 rho 重表达为 base 法线下的有符号距离
        rho2 = rho * (math.cos(theta) * math.cos(base) + math.sin(theta) * math.sin(base))
        placed = False
        for r in reps:
            if abs(r[1] - base) <= 1e-3 and abs(r[0] - rho2) <= rho_tol:
                r[0] = (r[0] * r[2] + rho2) / (r[2] + 1)
                r[2] += 1
                placed = True
                break
        if not placed:
            reps.append([rho2, base, 1])
    return [(r[0], r[1]) for r in reps]


# --------------------------------------------------------------------------- #
# 3. 直线交点
# --------------------------------------------------------------------------- #
def _intersection(rho1, theta1, rho2, theta2):
    a1, b1 = math.cos(theta1), math.sin(theta1)
    a2, b2 = math.cos(theta2), math.sin(theta2)
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-6:
        return None
    x = (rho1 * b2 - rho2 * b1) / det
    y = (rho2 * a1 - rho1 * a2) / det
    return (x, y)


# --------------------------------------------------------------------------- #
# 4. 每条直线 → 截断成墙段
# --------------------------------------------------------------------------- #
def _build_walls(bin_inv, lines):
    h, w = bin_inv.shape
    # 所有直线的交点
    inters = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            p = _intersection(lines[i][0], lines[i][1], lines[j][0], lines[j][1])
            if p and -50 <= p[0] <= w + 50 and -50 <= p[1] <= h + 50:
                inters.append(p)

    nodes = []
    def get_node(p, tol=10):
        for idx, n in enumerate(nodes):
            if abs(n[0] - p[0]) <= tol and abs(n[1] - p[1]) <= tol:
                return idx
        nodes.append([p[0], p[1]])
        return len(nodes) - 1

    walls = []
    span = math.hypot(w, h)
    for rho, theta in lines:
        a, b = math.cos(theta), math.sin(theta)
        # 直线上一点（垂足）
        fx, fy = rho * a, rho * b
        dx, dy = -b, a  # 方向向量
        # 沿 t 采样：检查采样点及其法线方向邻域(±3px)是否有墙像素，
        # 容忍 Hough 估计 rho 的偏移，避免错过窄墙线。
        def has_wall(tx, ty):
            for o in range(-3, 4):
                xx = int(round(tx + a * o)); yy = int(round(ty + b * o))
                if 0 <= xx < w and 0 <= yy < h and bin_inv[yy, xx] > 0:
                    return True
            return False

        on = []
        step = 2
        for t in range(-int(span), int(span), step):
            x = fx + t * dx
            y = fy + t * dy
            if has_wall(x, y):
                on.append(t)
        if not on:
            continue
        on.sort()
        # 合并间隔 <= step*1.8 的连续点
        segs_t = []
        s0 = on[0]; prev = on[0]
        for t in on[1:]:
            if t - prev <= step * 1.8:
                prev = t
            else:
                segs_t.append((s0, prev)); s0 = t; prev = t
        segs_t.append((s0, prev))
        # 用交点切割（交点投影 t）
        for t_int in [round((ix - fx) * dx + (iy - fy) * dy, 1) for ix, iy in inters]:
            segs_t = _split_segs(segs_t, t_int)
        # 生成墙段
        for t0, t1 in segs_t:
            if t1 - t0 < 8:  # 太短忽略
                continue
            p_a = (fx + t0 * dx, fy + t0 * dy)
            p_b = (fx + t1 * dx, fy + t1 * dy)
            ia = get_node(p_a); ib = get_node(p_b)
            if ia != ib:
                walls.append((ia, ib))
    return walls, nodes


def _split_segs(segs_t, t):
    """若 t 落在某区间内部，从 t 处切开。"""
    out = []
    for s0, s1 in segs_t:
        if s0 < t < s1:
            out.append((s0, t)); out.append((t, s1))
        else:
            out.append((s0, s1))
    return out


# --------------------------------------------------------------------------- #
# 5. 坐标清理
# --------------------------------------------------------------------------- #
def _normalize(nodes, walls, grid=10):
    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]
    minx, miny = min(xs), min(ys)
    snapped = [[round((n[0] - minx) / grid) * grid, round((n[1] - miny) / grid) * grid]
               for n in nodes]
    return snapped, walls, (minx, miny)


# --------------------------------------------------------------------------- #
# 6. 房间多边形（基于已确认墙段重绘 → flood-fill，保证封闭）
# --------------------------------------------------------------------------- #
def _extract_rooms(nodes, walls_px, minx, miny):
    """用已确认的墙段图重绘实心墙带，再 flood-fill 出闭合房间区域。

    比直接对原始二值图 flood 更稳：墙段是算法确认的，重绘加粗后必封闭。
    """
    if not nodes:
        return []
    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]
    w = int(max(xs)) + 20; h = int(max(ys)) + 20
    canvas = np.zeros((h, w), np.uint8)
    for a, b in walls_px:
        n1, n2 = nodes[a], nodes[b]
        cv2.line(canvas, (int(round(n1[0])), int(round(n1[1]))),
                 (int(round(n2[0])), int(round(n2[1]))), 255, 6)
    # 轻微膨胀确保节点处闭合
    canvas = cv2.dilate(canvas, np.ones((3, 3), np.uint8), iterations=1)
    inv = cv2.bitwise_not(canvas)
    flood = inv.copy()
    cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 255)
    interior = cv2.bitwise_not(flood)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(interior, 8)
    rooms = []
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] < 40 * 40:
            continue
        contours, _ = cv2.findContours(
            (labels == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        poly = cv2.approxPolyDP(c, 6, True).reshape(-1, 2)
        if len(poly) < 3:
            continue
        rooms.append([[int(x - minx), int(y - miny)] for x, y in poly])
    return rooms


# --------------------------------------------------------------------------- #
# 7. 门洞启发式
# --------------------------------------------------------------------------- #
def _detect_openings(bin_inv, walls_px, nodes, scale):
    """沿每条墙段在原始墙线图上扫描，找墙像素中断处 → 门/窗洞。

    比"共线墙段间 gap"更稳：即便闭运算把洞连上，原始图仍保留缺口。
    """
    h, w = bin_inv.shape
    openings = []
    oid = 0
    for (a, b) in walls_px:
        n1, n2 = nodes[a], nodes[b]
        is_h = abs(n1[1] - n2[1]) <= abs(n1[0] - n2[0])
        # 沿墙段方向采样，统计墙像素连续/中断
        x0, y0 = n1; x1, y1 = n2
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 30:
            continue
        steps = max(2, int(length / 4))
        on = []
        for s in range(steps + 1):
            t = s / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            # 邻域检查（含法线方向，避免窄墙 miss）
            a_ang = math.atan2(y1 - y0, x1 - x0)
            na, nb = -math.sin(a_ang), math.cos(a_ang)
            found = False
            for o in range(-3, 4):
                xx = int(round(x + na * o)); yy = int(round(y + nb * o))
                if 0 <= xx < w and 0 <= yy < h and bin_inv[yy, xx] > 0:
                    found = True; break
            on.append(found)
        # 找中断区间（连续 False 段）
        i = 0
        while i < len(on):
            if not on[i]:
                j = i
                while j < len(on) and not on[j]:
                    j += 1
                gap_px = (j - i) / steps * length
                gap_mm = gap_px * scale
                if 500 <= gap_mm <= 1600:
                    # 缺口中点（像素）
                    tm = (i + j) / 2 / steps
                    mx = x0 + (x1 - x0) * tm
                    my = y0 + (y1 - y0) * tm
                    otype = "door" if gap_mm <= 1100 else "window"
                    oid += 1
                    openings.append({"id": f"o_auto_{oid}", "type": otype,
                                     "pos_px": [round(mx, 1), round(my, 1)],
                                     "width_mm": round(min(gap_mm, 1100) if otype == "door" else gap_mm)})
                i = j
            else:
                i += 1
    return openings


# --------------------------------------------------------------------------- #
# 8. 比例校准
# --------------------------------------------------------------------------- #
def _calibrate(gray, bin_inv):
    scale, calibrated, note = None, False, ""
    longest = 0
    # 最长墙（用 bin_inv 投影估计）
    proj_x = bin_inv.max(axis=0)
    proj_y = bin_inv.max(axis=1)
    # 这里 longest 由调用方传入更准；改为从 lines 估，简单用图像对角线比例下限
    try:
        p = subprocess.run(
            ["tesseract", "-", "stdout", "-l", "eng", "--psm", "7", "-c",
             "tessedit_char_whitelist=0123456789"],
            input=cv2.imencode(".png", gray)[1].tobytes(), capture_output=True,
        )
        nums = [int(x) for x in re.findall(r"\d{3,5}", p.stdout.decode("utf-8", "ignore"))
                if 1000 <= int(x) <= 20000]
        if nums:
            # 找最长墙像素跨度
            cols = np.where(proj_x > 0)[0]
            rows = np.where(proj_y > 0)[0]
            max_span = max(
                (cols.max() - cols.min()) if len(cols) else 0,
                (rows.max() - rows.min()) if len(rows) else 0,
            )
            if max_span > 0:
                dim = max(nums)
                scale = dim / max_span
                calibrated = True
                note = f"OCR 标注校准：{dim}mm / {max_span:.0f}px"
    except Exception:
        pass
    if scale is None:
        cols = np.where(proj_x > 0)[0]; rows = np.where(proj_y > 0)[0]
        max_span = max((cols.max() - cols.min()) if len(cols) else 0,
                       (rows.max() - rows.min()) if len(rows) else 0)
        if max_span > 0:
            scale = 6000.0 / max_span
            note = "未识别到尺寸标注，按最长边≈6000mm 估算（请在校正视图确认）"
    return scale, calibrated, note


# --------------------------------------------------------------------------- #
# 9. 主入口
# --------------------------------------------------------------------------- #
def recognize_cv(image_path: str) -> dict:
    bin_inv, bin_raw, gray = _load_binary(image_path)
    lines = _hough_lines(bin_inv)
    if not lines:
        raise ValueError("未检测到墙线，可能不是线稿类户型图")

    walls_px, nodes = _build_walls(bin_inv, lines)
    if not walls_px:
        raise ValueError("墙线提取为空，可能是噪声过多或非正交户型")
    nodes, walls_px, (minx, miny) = _normalize(nodes, walls_px)

    scale, calibrated, note = _calibrate(gray, bin_inv)
    if scale is None:
        scale = 0.1

    def px2mm(p):
        return [round(p[0] * scale, 1), round(p[1] * scale, 1)]

    walls = []
    for i, (a, b) in enumerate(walls_px):
        n1, n2 = nodes[a], nodes[b]
        length = math.hypot(n1[0] - n2[0], n1[1] - n2[1]) * scale
        walls.append({
            "id": f"w_auto_{i + 1}",
            "p1": px2mm(n1), "p2": px2mm(n2),
            "thickness": 200,
            "type": "bearing" if length > 3000 else "partition",
            "height": 2800,
        })

    rooms = []
    for poly_px in _extract_rooms(nodes, walls_px, minx, miny):
        poly = [px2mm([round(x / 10) * 10, round(y / 10) * 10]) for x, y in poly_px]
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys)) / 1_000_000.0
        rooms.append({"id": f"r_auto_{len(rooms) + 1}",
                      "name": f"房间{len(rooms) + 1}", "type": "unknown",
                      "poly": poly, "area": round(area, 2)})
    if not rooms:
        xs_mm = [w["p1"][0] for w in walls] + [w["p2"][0] for w in walls]
        ys_mm = [w["p1"][1] for w in walls] + [w["p2"][1] for w in walls]
        poly = [[min(xs_mm), min(ys_mm)], [max(xs_mm), min(ys_mm)],
                [max(xs_mm), max(ys_mm)], [min(xs_mm), max(ys_mm)]]
        area = (max(xs_mm) - min(xs_mm)) * (max(ys_mm) - min(ys_mm)) / 1_000_000.0
        rooms.append({"id": "r_auto_1", "name": "整体空间", "type": "unknown",
                      "poly": poly, "area": round(area, 2)})

    openings = _detect_openings(bin_raw, walls_px, nodes, scale)

    house = {
        "walls": walls, "openings": openings, "rooms": rooms, "fixed": [],
        "meta": {"source": "cv_local", "calibrated": calibrated,
                 "scale_mm_per_px": round(float(scale), 4), "note": note},
    }
    house["original_walls"] = [dict(w) for w in walls]
    return _to_jsonable(house)


def _to_jsonable(obj):
    """递归把 numpy 类型转为 Python 原生类型，便于 JSON 序列化。"""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj
