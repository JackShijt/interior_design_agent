"""规划 Agent（MVP：占位；生产：LLM 空间规划推理）。

把自然语言需求翻译成"房间功能+家具清单草案"，供 generator 使用。
"""
def plan(scheme: dict, user_need: str) -> dict:
    """返回规划策略（MVP 简化：仅记录需求关键词）。"""
    return {
        "need": user_need,
        "strategy": "controlled_assembly",  # 路线 A
        "note": "MVP 占位，生产接 LLM 做空间分配推理",
    }
