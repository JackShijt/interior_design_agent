"""规划 Agent：把自然语言需求翻译成"房间功能 + 家具清单草案"，供 generator 使用。

生产：调用 LLM（OpenAI 兼容接口）做空间分配语义推理。
MVP/降级：无 API Key 时走规则占位逻辑。
"""
import os
import json

try:
    from openai import OpenAI
except ImportError:  # openai 未安装时降级
    OpenAI = None

SYSTEM_PROMPT = (
    "你是室内设计规划助手。用户给出装修需求（如'现代简约 两口之家 多收纳'），"
    "请输出 JSON：{\"rooms\":[{\"type\":\"bedroom\",\"functions\":[...]}],"
    "\"furniture_draft\":[{\"cat\":\"wardrobe\",\"qty\":1}],\"style\":\"modern_minimal\"}。"
    "只做语义推理，不要编造具体毫米尺寸。cat 取值限于 wardrobe/bed/sofa 等构件类别。"
)


def _build_client():
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key or OpenAI is None:
        return None
    base_url = os.environ.get("LLM_BASE_URL")  # 兼容 DeepSeek/Qwen 等
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def plan(scheme: dict, user_need: str) -> dict:
    """生产：真实 LLM 调用。无 Key 时自动降级到 plan_with_mock。"""
    client = _build_client()
    if client is None:
        return plan_with_mock(scheme, user_need)

    model = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_need},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError):
        return plan_with_mock(scheme, user_need)
    # 安全护栏：只允许已知 cat
    known = {"wardrobe", "bed", "sofa"}
    for item in data.get("furniture_draft", []):
        if item.get("cat") not in known:
            item["cat"] = "wardrobe"
    return data


def plan_with_mock(scheme: dict, user_need: str) -> dict:
    """无 Key 降级：基于关键词的占位规划（不编造毫米尺寸）。"""
    need = (user_need or "").lower()
    furniture_draft = []
    if "收纳" in need or "衣柜" in need:
        furniture_draft.append({"cat": "wardrobe", "qty": 1})
    if "床" in need or "卧室" in need or "两口" in need:
        furniture_draft.append({"cat": "bed", "qty": 1})
    if "沙发" in need or "客厅" in need:
        furniture_draft.append({"cat": "sofa", "qty": 1})
    if not furniture_draft:
        furniture_draft.append({"cat": "wardrobe", "qty": 1})

    style = "modern_minimal"
    if "暖" in need or "温馨" in need:
        style = "warm"

    return {
        "rooms": [{"type": "bedroom", "functions": ["sleep", "storage"]}],
        "furniture_draft": furniture_draft,
        "style": style,
        "note": "MVP mock 规划，未调用 LLM",
    }
