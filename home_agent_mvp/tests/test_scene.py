"""第 9 周：渲染场景转换冒烟测试。"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme():
    with open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8") as f:
        s = json.load(f)
    if not s["design"].get("furniture"):
        s["design"]["furniture"] = [
            {"id": "f1", "cat": "wardrobe", "model": "wd_01",
             "pos": [100, 100], "size": [1800, 600, 2400]},
        ]
    return s


def test_to_scene_structure():
    from render import scene
    data = scene.to_scene(_scheme())
    assert data["unit"] == "mm"
    assert data["scale"] == 0.01
    assert len(data["walls"]) > 0
    assert len(data["furniture"]) > 0
    # 每件家具含必要字段
    for f in data["furniture"]:
        assert "pos" in f and "size" in f and "cat" in f


def test_wall_to_box():
    from render import scene
    box = scene.wall_to_box({"p1": [0, 0], "p2": [4200, 0], "height": 2800, "thickness": 200})
    # 水平墙：x 方向延伸
    assert box["size"][0] == 4200
    assert box["size"][2] == 2800
    assert box["center"][0] == 2100
