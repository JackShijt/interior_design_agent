"""约束引擎：加载 YAML 规则，对方案 JSON 做 block/warn/optimize 三级校验。"""
import yaml
import os

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "constraints.yaml")


def load_rules(path: str = RULES_PATH) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def _matches(cond: dict, scheme: dict) -> bool:
    """极简条件匹配（生产环境换规则引擎 DSL 解析）。

    安全类规则（A 类）优先读取 scheme["pending_actions"] 中的显式意图；
    删除类额外对比 original_walls 基线，防止"墙凭空消失"被漏检。
    支持条件：
      - remove_wall + wall_type=bearing
      - open_hole + wall_type=bearing + width_gt
      - move + element in [pipe_shaft, flue]
      - set_material + room_type + material_not_in
      - corridor_width_lt
      - furniture=wardrobe + depth_not_in
      - furniture=bed + side_clearance_lt
    """
    action = cond.get("action")
    intents = scheme.get("pending_actions", [])

    if action == "remove_wall":
        # 1) 显式删除意图
        for it in intents:
            if it.get("action") == "remove_wall" and it.get("wall_type") == cond.get("wall_type"):
                return True
        # 2) 基线对比：原承重墙消失
        original = scheme["house"].get("original_walls", scheme["house"]["walls"])
        current_ids = {w["id"] for w in scheme["house"]["walls"]}
        for w in original:
            if w.get("type") == cond.get("wall_type") and w["id"] not in current_ids:
                return True

    if action == "open_hole":
        for it in intents:
            if it.get("action") == "open_hole" and it.get("wall_type") == cond.get("wall_type") \
               and it.get("width", 0) > cond.get("width_gt", 1e9):
                return True

    if action == "move":
        for it in intents:
            if it.get("action") == "move" and it.get("element") in cond.get("element", []):
                return True

    if action == "set_material":
        # 简化：检查 design.harddecor 中对应房间材质
        for hd in scheme["design"].get("harddecor", []):
            if hd.get("room") == cond.get("room_type"):
                if hd.get("material") not in cond.get("material_not_in", []):
                    return False
        return True

    if action == "corridor_width_lt":
        # 简化：用房间最小边长近似 corridors
        for r in scheme["house"].get("rooms", []):
            poly = r.get("poly", [])
            if poly:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                if min(w, h) < cond.get("corridor_width_lt", 0):
                    return True

    if action in ("furniture_depth", "furniture_clearance"):
        for f in scheme["design"].get("furniture", []):
            if f.get("cat") == cond.get("furniture"):
                if action == "furniture_depth":
                    d = f["size"][1]
                    lo, hi = cond.get("depth_not_in", [0, 1e9])
                    # 仅在严格超出推荐区间 [lo, hi] 时标记
                    if d < lo or d > hi:
                        return True
                if action == "furniture_clearance":
                    # 简化：用 pos 到墙距离近似
                    clearance = f["pos"][0]
                    if clearance < cond.get("side_clearance_lt", 0):
                        return True

    # 兼容：规则 condition 直接以 furniture + depth_not_in / side_clearance_lt
    # 表达（无需 action 字段，便于产品/算法配置）。
    if cond.get("furniture") and (cond.get("depth_not_in") or cond.get("side_clearance_lt")):
        for f in scheme["design"].get("furniture", []):
            if f.get("cat") != cond.get("furniture"):
                continue
            if cond.get("depth_not_in"):
                d = f["size"][1]
                lo, hi = cond.get("depth_not_in", [0, 1e9])
                if d < lo or d > hi:
                    return True
            if cond.get("side_clearance_lt"):
                clearance = f["pos"][0]
                if clearance < cond.get("side_clearance_lt", 0):
                    return True
    return False


def evaluate(scheme: dict, rules: list = None) -> tuple:
    """返回 (passed: bool, report: dict)。block 级则 passed=False。"""
    if rules is None:
        rules = load_rules()
    report = {"block": [], "warn": [], "optimize": []}
    for rule in rules:
        if _matches(rule["condition"], scheme):
            lvl = rule["level"]
            msg = rule["action"].get("message", rule["name"])
            if lvl == "block":
                report["block"].append(msg)
            elif lvl == "warn_confirm":
                report["warn"].append(msg)
            else:
                report["optimize"].append(msg)
    passed = len(report["block"]) == 0
    return passed, report


if __name__ == "__main__":
    import json
    s = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "scheme.json"), encoding="utf-8"))
    print(evaluate(s))
