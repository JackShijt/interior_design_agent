"""渲染层（MVP：Mock；生产：接 KooEngine 类云渲染 / Three.js 前端）。"""


def render(scheme: dict) -> dict:
    """返回渲染任务描述（MVP 占位）。生产返回视频流/图片 URL。"""
    return {
        "status": "rendered",
        "mode": "mock",
        "furniture_count": len(scheme["design"].get("furniture", [])),
        "style": scheme["design"].get("style"),
        "note": "生产环境接 GPU 集群实时光追，支持增量重渲染",
    }
