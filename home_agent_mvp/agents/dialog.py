"""对话 Agent：把自然语言修改映射为对 scheme JSON 的结构化编辑。

生产：LLM Function Calling（edit_furniture / apply_style / move_furniture /
      add_furniture / remove_furniture），所有修改须过约束引擎，冲突返回替代方案。
降级：无 LLM_API_KEY 时回退正则解析（MVP 占位逻辑），保持闭环可用。
"""
import os
import re

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from agents import constraint

CAT_KEYWORDS = {"wardrobe": "衣柜", "bed": "床", "sofa": "沙发"}


# ---------------------------------------------------------------------------
# LLM Function Calling 定义
# ---------------------------------------------------------------------------
FUNCTIONS = [
    {
        "name": "edit_furniture",
        "description": "修改某类家具的尺寸（长/宽/高/深，单位 mm）或数量",
        "parameters": {
            "type": "object",
            "properties": {
                "cat": {"type": "string", "enum": ["wardrobe", "bed", "sofa"]},
                "dim": {"type": "string", "enum": ["length", "width", "height", "depth"]},
                "delta_mm": {"type": "integer", "description": "尺寸变化量（mm），可正可负"},
                "qty": {"type": "integer", "description": "设置数量（可选）"},
            },
            "required": ["cat"],
        },
    },
    {
        "name": "apply_style",
        "description": "切换整体风格",
        "parameters": {
            "type": "object",
            "properties": {
                "style": {"type": "string", "enum": ["modern_minimal", "warm"]},
            },
            "required": ["style"],
        },
    },
    {
        "name": "move_furniture",
        "description": "移动某类家具（MVP 仅记录意图）",
        "parameters": {
            "type": "object",
            "properties": {
                "cat": {"type": "string", "enum": ["wardrobe", "bed", "sofa"]},
                "to": {"type": "string", "description": "目标位置描述，如'靠窗'"},
            },
            "required": ["cat", "to"],
        },
    },
    {
        "name": "add_furniture",
        "description": "新增一件家具",
        "parameters": {
            "type": "object",
            "properties": {
                "cat": {"type": "string", "enum": ["wardrobe", "bed", "sofa"]},
            },
            "required": ["cat"],
        },
    },
    {
        "name": "remove_furniture",
        "description": "移除某类家具",
        "parameters": {
            "type": "object",
            "properties": {
                "cat": {"type": "string", "enum": ["wardrobe", "bed", "sofa"]},
            },
            "required": ["cat"],
        },
    },
    {
        "name": "remove_wall",
        "description": "拆除墙体（红线操作，需人工确认；承重墙禁止）",
        "parameters": {
            "type": "object",
            "properties": {
                "wall_type": {"type": "string", "enum": ["bearing", "partition", "suspect_load_bearing"]},
            },
            "required": ["wall_type"],
        },
    },
    {
        "name": "open_hole",
        "description": "在墙上开洞（红线操作，承重墙开洞受限）",
        "parameters": {
            "type": "object",
            "properties": {
                "wall_type": {"type": "string", "enum": ["bearing", "partition"]},
                "width_mm": {"type": "integer", "description": "开洞宽度 mm"},
            },
            "required": ["wall_type"],
        },
    },
]


# ---------------------------------------------------------------------------
# 约束检查 + 替代方案
# ---------------------------------------------------------------------------
def _check(scheme, rules):
    ok, report = constraint.evaluate(scheme, rules)
    return ok, report


def _alternative(report):
    blocks = report.get("block", [])
    if blocks:
        return "无法执行： " + "；".join(blocks) + " 建议采用替代方案（如垭口/半墙）。"
    return None


# ---------------------------------------------------------------------------
# 各 Function 的执行实现
# ---------------------------------------------------------------------------
_DIM_INDEX = {"length": 0, "width": 1, "height": 2, "depth": 1}


def _apply_edit(scheme, args):
    cat = args["cat"]
    changed = []
    for f in scheme["design"]["furniture"]:
        if f["cat"] != cat:
            continue
        if "dim" in args and "delta_mm" in args:
            idx = _DIM_INDEX[args["dim"]]
            f["size"][idx] = max(0, f["size"][idx] + args["delta_mm"])
            changed.append(f"{CAT_KEYWORDS[cat]} {args['dim']}→{f['size'][idx]}mm")
        if "qty" in args:
            # qty 仅做提示，实际数量由 add/remove 调整
            changed.append(f"{CAT_KEYWORDS[cat]} 数量意图={args['qty']}")
    return "；".join(changed) or f"未找到 {CAT_KEYWORDS.get(cat, cat)}"


def _exec_function(name, args, scheme, rules):
    """执行一个 function call，返回 (scheme, message)。冲突时 message 含替代方案。"""
    if name == "apply_style":
        scheme["design"]["style"] = args["style"]
        msg = f"风格切换为 {args['style']}"
    elif name == "edit_furniture":
        msg = _apply_edit(scheme, args)
    elif name == "move_furniture":
        msg = f"{CAT_KEYWORDS.get(args['cat'], args['cat'])} 移动意图：{args.get('to')}（MVP 记录）"
    elif name == "add_furniture":
        cat = args["cat"]
        scheme["design"]["furniture"].append({
            "id": f"f_auto_{len(scheme['design']['furniture']) + 1}",
            "cat": cat, "model": f"{cat}_01",
            "pos": [200, 200], "size": [1000, 600, 2000], "price": 1000,
        })
        msg = f"已添加 {CAT_KEYWORDS.get(cat, cat)}"
    elif name == "remove_furniture":
        cat = args["cat"]
        before = len(scheme["design"]["furniture"])
        scheme["design"]["furniture"] = [f for f in scheme["design"]["furniture"] if f["cat"] != cat]
        msg = f"已移除 {CAT_KEYWORDS.get(cat, cat)}（{before - len(scheme['design']['furniture'])} 件）"
    elif name == "remove_wall":
        # 红线操作：记录意图到 pending_actions，由约束引擎判定是否阻断
        scheme.setdefault("pending_actions", []).append(
            {"action": "remove_wall", "wall_type": args["wall_type"]})
        msg = f"申请拆除 {args['wall_type']} 墙（需人工确认）"
    elif name == "open_hole":
        width = args.get("width_mm", 0)
        scheme.setdefault("pending_actions", []).append(
            {"action": "open_hole", "wall_type": args["wall_type"], "width": width})
        msg = f"申请在 {args['wall_type']} 墙开洞（宽 {width}mm，需人工确认）"
    else:
        return scheme, "未知指令。"

    # 必经约束校验
    ok, report = _check(scheme, rules)
    if not ok:
        alt = _alternative(report)
        # 红线阻断：保留意图供 /confirm_demolition 人工确认
        return scheme, "[需人工确认] " + (alt or "修改违反约束。")
    return scheme, msg


# ---------------------------------------------------------------------------
# 正则降级（无 Key）
# ---------------------------------------------------------------------------
def _price_for(cat, size):
    base = {"wardrobe": 3200, "bed": 2600, "sofa": 3500}.get(cat, 1000)
    return int(base + size[0] * 1.0)


def _regex_handle(scheme, text):
    text = text or ""
    changed = False
    msgs = []
    cat_keywords = {"衣柜": "wardrobe", "柜": "wardrobe", "床": "bed", "沙发": "sofa"}
    dim_map = {"长": 0, "宽": 1, "高": 2, "深": 1}
    target_cat = None
    for kw, cat in cat_keywords.items():
        if kw in text:
            target_cat = cat
            break
    num_m = re.search(r"(\d+)\s*cm", text)
    dim_m = re.search(r"加?\s*(长|宽|高|深)", text)
    if target_cat and num_m and dim_m:
        idx = dim_map[dim_m.group(1)]
        delta = int(num_m.group(1)) * 10
        for f in scheme["design"]["furniture"]:
            if f["cat"] == target_cat:
                f["size"][idx] += delta
                f["price"] = _price_for(f["cat"], f["size"])
                changed = True
                msgs.append(f"{CAT_KEYWORDS.get(f['cat'], f['cat'])} {dim_m.group(1)} 调整为 {f['size'][idx]}mm")
                break
    if not changed:
        if "暖" in text or "温馨" in text:
            scheme["design"]["style"] = "warm"
            changed = True
            msgs.append("风格切换为 warm")
        elif "现代" in text or "简约" in text:
            scheme["design"]["style"] = "modern_minimal"
            changed = True
            msgs.append("风格切换为 modern_minimal")

    # 移动意图（降级简化）
    if not changed and ("移" in text or "靠" in text):
        for kw, cat in cat_keywords.items():
            if kw in text:
                to = "靠窗" if "窗" in text else "新位置"
                changed = True
                msgs.append(f"{CAT_KEYWORDS[cat]} 移动意图：{to}（MVP 记录）")
                break

    # 新增意图
    if not changed and ("加" in text or "添" in text):
        for kw, cat in cat_keywords.items():
            if kw in text:
                scheme["design"]["furniture"].append({
                    "id": f"f_auto_{len(scheme['design']['furniture']) + 1}",
                    "cat": cat, "model": f"{cat}_01",
                    "pos": [200, 200], "size": [1000, 600, 2000], "price": 1000,
                })
                changed = True
                msgs.append(f"已添加 {CAT_KEYWORDS[cat]}")
                break

    # 移除意图
    if not changed and ("移除" in text or "去掉" in text or "删除" in text):
        for kw, cat in cat_keywords.items():
            if kw in text:
                before = len(scheme["design"]["furniture"])
                scheme["design"]["furniture"] = [f for f in scheme["design"]["furniture"] if f["cat"] != cat]
                changed = True
                msgs.append(f"已移除 {CAT_KEYWORDS[cat]}（{before - len(scheme['design']['furniture'])} 件）")
                break

    # 拆墙/开洞红线意图（降级简化）
    if not changed and ("拆" in text or "打掉" in text or "开洞" in text):
        if "承重" in text:
            wtype = "bearing"
        elif "隔" in text or "非承重" in text:
            wtype = "partition"
        else:
            wtype = "suspect_load_bearing"
        hole_m = re.search(r"开洞.*?(\d+)\s*mm", text) or re.search(r"(\d+)\s*mm.*?洞", text)
        width = int(hole_m.group(1)) if hole_m else 0
        action = "open_hole" if "洞" in text else "remove_wall"
        scheme.setdefault("pending_actions", []).append(
            {"action": action, "wall_type": wtype, **({"width": width} if action == "open_hole" else {})})
        changed = True
        msgs.append(f"申请{'开洞' if action == 'open_hole' else '拆除'} {wtype} 墙（需人工确认）")

    if not changed:
        return scheme, "暂未理解该指令（MVP 仅支持尺寸修改/风格切换/移动/增减/拆墙示例）。"
    return scheme, "；".join(msgs)


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def handle_command(scheme: dict, text: str):
    rules = constraint.load_rules()
    client = _build_client()
    if client is None:
        # 降级：正则
        scheme, msg = _regex_handle(scheme, text)
        ok, report = _check(scheme, rules)
        if not ok:
            return scheme, _alternative(report) or msg
        return scheme, msg

    model = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": text}],
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0.1,
    )
    msg_obj = resp.choices[0].message
    if msg_obj.function_call:
        import json
        name = msg_obj.function_call.name
        args = json.loads(msg_obj.function_call.arguments or "{}")
        return _exec_function(name, args, scheme, rules)
    # 没有 function call（纯闲聊/风格描述）
    return _regex_handle(scheme, text)


def _build_client():
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.environ.get("LLM_BASE_URL")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def dialog_with_mock(scheme: dict, text: str):
    """显式走正则降级，便于无 Key 环境测试（仍过约束校验）。"""
    scheme, msg = _regex_handle(scheme, text)
    rules = constraint.load_rules()
    ok, report = _check(scheme, rules)
    if not ok:
        return scheme, _alternative(report) or msg
    return scheme, msg
