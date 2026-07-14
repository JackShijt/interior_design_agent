"""渲染层：scheme JSON → Three.js 场景描述（纯数据结构，便于测试与前端消费）。

MVP：墙体+家具用轴对齐盒体（BoxGeometry）近似，单位为 mm，前端按 1:100 缩放展示。
生产：接 KooEngine 类云渲染 / 精细模型。
"""


def to_scene(scheme: dict) -> dict:
    """把 scheme 转换为 Three.js 场景描述。

    返回：
      {
        "unit": "mm",
        "scale": 0.01,           # 前端 1:100 缩放
        "walls": [{"p1":[x,y], "p2":[x,y], "height":h, "thickness":t, "type":...}],
        "rooms": [{"name":..., "poly":[[x,y],...]}],
        "furniture": [{"cat":..., "pos":[x,y], "size":[w,d,h], "model":...}],
        "style": "modern_minimal"
      }
    """
    house = scheme.get("house", {})
    design = scheme.get("design", {})

    walls = []
    for w in house.get("walls", []):
        walls.append({
            "p1": w.get("p1"),
            "p2": w.get("p2"),
            "height": w.get("height", 2800),
            "thickness": w.get("thickness", 200),
            "type": w.get("type", "partition"),
        })

    rooms = []
    for r in house.get("rooms", []):
        rooms.append({"name": r.get("name", ""), "poly": r.get("poly", []), "area": r.get("area")})

    openings = []
    for op in house.get("openings", []):
        openings.append({
            "id": op.get("id"),
            "wall_id": op.get("wall_id"),
            "type": op.get("type", "door"),
            "offset": op.get("offset", 0),
            "width": op.get("width", 900),
            "height": op.get("height", 2100),
        })

    furniture = []
    for f in design.get("furniture", []):
        furniture.append({
            "cat": f.get("cat"),
            "model": f.get("model"),
            "pos": f.get("pos", [0, 0]),
            "size": f.get("size", [1000, 600, 2000]),
        })

    return {
        "unit": scheme.get("unit", "mm"),
        "scale": 0.01,
        "walls": walls,
        "rooms": rooms,
        "openings": openings,
        "furniture": furniture,
        "style": design.get("style", "modern_minimal"),
    }


def wall_to_box(wall: dict) -> dict:
    """单段墙 → 盒体中心+尺寸（用于 Three.js BoxGeometry）。"""
    x1, y1 = wall["p1"]
    x2, y2 = wall["p2"]
    h = wall.get("height", 2800)
    t = wall.get("thickness", 200)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    # 沿较长边方向延伸，短边取厚度
    if dx >= dy:
        size = [max(dx, t), t, h]
    else:
        size = [t, max(dy, t), h]
    return {"center": [cx, cy, h / 2], "size": size}
