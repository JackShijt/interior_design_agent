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
# 全品类关键词（含组件库其余品类，补足生成器与对话的覆盖缺口）
CAT_KEYWORDS_FULL = {
    "wardrobe": ["衣柜", "衣帽间", "柜"], "bed": ["床"], "sofa": ["沙发"],
    "desk": ["书桌", "办公桌", "电脑桌"], "table": ["餐桌", "茶几"], "nightstand": ["床头柜"],
    "tv_cabinet": ["电视柜"], "cabinet": ["餐边柜", "书柜", "储物柜", "柜"], "kitchen": ["橱柜", "厨房"],
    "bath_cabinet": ["浴室柜", "卫浴柜", "卫生间柜"], "shelf": ["置物架", "飘窗柜"], "shoe_cabinet": ["鞋柜", "玄关柜"],
    "chair": ["餐椅", "办公椅", "椅子"],
}


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
            "pos": [200, 200], "size": [1000, 600, 2000],
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
# 参考图分析：提取风格标签（有视觉 LLM 走模型，无 Key 降级）
# ---------------------------------------------------------------------------
_STYLE_LABEL = {"modern_minimal": "现代简约", "warm": "温馨北欧"}
# 关键词 → 风格（供文本 / 降级判断）
_STYLE_HINTS = [
    (["暖", "温馨", "原木", "北欧", "奶油", "日式", "木色"], "warm"),
    (["现代", "简约", "极简", "冷", "工业", "轻奢", "黑白"], "modern_minimal"),
]


def analyze_reference(image_path: str, text: str = "") -> dict:
    """分析参考图，返回 {style, style_label, tags}。

    - 配置了视觉 LLM（LLM_API_KEY + 支持图片的 MODEL_NAME）时，调用模型识别风格标签；
    - 否则降级：结合对话文本关键词推断风格，给出通用标签，保证闭环可用。
    """
    client = _build_client()
    if client is not None and os.environ.get("VISION_ENABLED"):
        try:
            return _vision_reference(client, image_path, text)
        except Exception:
            pass  # 视觉失败安全回退降级

    # —— 降级：文本关键词 + 默认 ——
    style = None
    for kws, st in _STYLE_HINTS:
        if any(k in (text or "") for k in kws):
            style = st
            break
    style = style or "warm"   # 有参考图默认偏温馨（大多数参考图为家居暖调）
    tags = ["原木", "暖色", "自然"] if style == "warm" else ["简约", "线条感", "留白"]
    return {"style": style, "style_label": _STYLE_LABEL.get(style, style), "tags": tags}


def _vision_reference(client, image_path: str, text: str) -> dict:
    """调用视觉 LLM 识别参考图风格（需模型支持图片输入）。"""
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    model = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "text", "content": "这是一张室内设计参考图。请用 JSON 回答："
             "{\"style\":\"modern_minimal|warm\",\"tags\":[中文风格标签3个]}"
             f" 用户补充：{text}"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        temperature=0.1,
    )
    import json as _json
    raw = resp.choices[0].message.content or "{}"
    raw = raw[raw.find("{"): raw.rfind("}") + 1] or "{}"
    data = _json.loads(raw)
    style = data.get("style", "warm")
    return {"style": style, "style_label": _STYLE_LABEL.get(style, style),
            "tags": data.get("tags", [])}


# ---------------------------------------------------------------------------
# 正则降级（无 Key）
# ---------------------------------------------------------------------------
def _regex_handle(scheme, text, context=None):
    """解析口语指令并改 scheme。支持上下文指代消解（如"再大点""换个风格"）。

    context: 可选 dict，含上一轮操作记录（last_cat / last_dim / last_style / history）。
    """
    text = text or ""
    changed = False
    msgs = []
    context = context or {}

    # —— 指代消解：从上下文推断目标品类/维度 ——
    # 注意：CAT_KEYWORDS 的 key 是英文类别，value 才是中文关键词，需用 value 匹配文本
    target_cat = None
    for cat, kw in CAT_KEYWORDS.items():
        if kw in text:
            target_cat = cat
            break
    if target_cat is None and context.get("last_cat") and re.search(r"再|继续|大点|小点|长点|短点|宽点|窄点|高一点", text):
        target_cat = context["last_cat"]  # 指代上一轮操作的家具

    # —— 尺寸增量（支持"加长30cm"与"再大点"）——
    dim_map = {"长": 0, "宽": 1, "高": 2, "深": 1}
    dim_m = re.search(r"加?\s*(长|宽|高|深)", text) or (re.search(r"(长|宽|高|深)点", text) if context.get("last_dim") else None)
    num_m = re.search(r"(\d+)\s*cm", text)
    delta = 0
    if target_cat:
        if num_m and dim_m:
            idx = dim_map[dim_m.group(1)]
            delta = int(num_m.group(1)) * 10
        elif re.search(r"再|继续", text) and re.search(r"大|长|宽|高|增加|加", text):
            # "再大点"：沿上一轮维度 +100mm
            idx = dim_map.get(context.get("last_dim"), 0)
            delta = 100
        elif re.search(r"小|短|窄|减|降低", text):
            idx = dim_map.get(context.get("last_dim") or "宽", 1)
            delta = -100
        if delta != 0:
            for f in scheme["design"]["furniture"]:
                if f["cat"] == target_cat:
                    f["size"][idx] = max(0, f["size"][idx] + delta)
                    changed = True
                    dim_name = [k for k, v in dim_map.items() if v == idx][0]
                    msgs.append(f"{CAT_KEYWORDS.get(f['cat'], f['cat'])} {dim_name} 调整为 {f['size'][idx]}mm")
                    context["last_cat"] = target_cat
                    context["last_dim"] = dim_name
                    break

    # —— 风格切换（支持"换个风格""再温馨点"）——
    if not changed:
        if "暖" in text or "温馨" in text:
            scheme["design"]["style"] = "warm"; changed = True; msgs.append("风格切换为 warm")
            context["last_style"] = "warm"
        elif "现代" in text or "简约" in text:
            scheme["design"]["style"] = "modern_minimal"; changed = True; msgs.append("风格切换为 modern_minimal")
            context["last_style"] = "modern_minimal"
        elif re.search(r"换个风格|换风格|再\s*(温馨|暖|现代|简约|极简)\s*点", text):
            # 在 modern_minimal / warm 间切换；无历史时默认从 modern_minimal 切到 warm
            last = context.get("last_style") or scheme["design"].get("style") or "modern_minimal"
            nxt = "warm" if last == "modern_minimal" else "modern_minimal"
            scheme["design"]["style"] = nxt; changed = True; msgs.append(f"风格切换为 {nxt}")
            context["last_style"] = nxt

    # —— 移动意图（降级简化）——
    if not changed and ("移" in text or "靠" in text):
        tcat = target_cat or context.get("last_cat")
        if tcat:
            to = "靠窗" if "窗" in text else "新位置"
            changed = True
            msgs.append(f"{CAT_KEYWORDS.get(tcat, tcat)} 移动意图：{to}（MVP 记录）")
            context["last_cat"] = tcat

    # —— 新增意图（全品类）——
    if not changed and ("加" in text or "添" in text or "来个" in text or "一组" in text):
        for cat, kws in CAT_KEYWORDS_FULL.items():
            if any(k in text for k in kws):
                scheme["design"]["furniture"].append({
                    "id": f"f_auto_{len(scheme['design']['furniture']) + 1}",
                    "cat": cat, "model": f"{cat}_01",
                    "pos": [200, 200], "size": [1000, 600, 2000],
                })
                changed = True
                msgs.append(f"已添加 {CAT_KEYWORDS.get(cat, cat)}")
                context["last_cat"] = cat
                break

    # —— 移除意图（全品类）——
    if not changed and ("移除" in text or "去掉" in text or "删除" in text):
        for cat, kws in CAT_KEYWORDS_FULL.items():
            if any(k in text for k in kws):
                before = len(scheme["design"]["furniture"])
                scheme["design"]["furniture"] = [f for f in scheme["design"]["furniture"] if f["cat"] != cat]
                changed = True
                msgs.append(f"已移除 {CAT_KEYWORDS.get(cat, cat)}（{before - len(scheme['design']['furniture'])} 件）")
                break

    # —— 拆墙/开洞红线意图（降级简化）——
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
        return scheme, "暂未理解该指令（MVP 支持：尺寸增减/风格切换/移动/增减家具/拆墙开洞，可说'再大点''换个风格'）。", context
    return scheme, "；".join(msgs), context


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def handle_command(scheme: dict, text: str, context: dict = None):
    """处理一句对话指令。context 为会话上下文（指代消解用），会被原地更新。"""
    rules = constraint.load_rules()
    client = _build_client()
    if client is None:
        # 降级：正则（带上下文指代消解）
        scheme, msg, context = _regex_handle(scheme, text, context or {})
        ok, report = _check(scheme, rules)
        if not ok:
            return scheme, _alternative(report) or msg, context
        return scheme, msg, context

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
        scheme, msg = _exec_function(name, args, scheme, rules)
        return scheme, msg, context
    # 没有 function call（纯闲聊/风格描述）→ 正则兜底并保留上下文
    scheme, msg, context = _regex_handle(scheme, text, context or {})
    ok, report = _check(scheme, rules)
    if not ok:
        return scheme, _alternative(report) or msg, context
    return scheme, msg, context


def _build_client():
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.environ.get("LLM_BASE_URL")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def dialog_with_mock(scheme: dict, text: str, context: dict = None):
    """显式走正则降级，便于无 Key 环境测试（仍过约束校验，支持上下文指代）。"""
    scheme, msg, context = _regex_handle(scheme, text, context or {})
    rules = constraint.load_rules()
    ok, report = _check(scheme, rules)
    if not ok:
        return scheme, _alternative(report) or msg, context
    return scheme, msg, context
