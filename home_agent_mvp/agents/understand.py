"""理解 Agent：户型识别。

生产接口签名保持一致，便于后续替换：
    recognize(image_path: str) -> dict  # 返回结构化 house 对象

MVP 策略：
  1. 若配置了外部识别服务（RECOGNITION_API_URL + RECOGNITION_API_KEY），
     调用其 API 做真实识别，并归一化为 house 结构；
  2. 未配置 / 调用失败时，回退到内置 Mock 户型，保证开发期闭环不中断。

无论何种来源，都会在返回前写入 original_walls 基线，供约束引擎检测承重墙移除。
"""
import json
import os

SCHEME_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scheme.json")


def _mock_house() -> dict:
    with open(SCHEME_PATH, "r", encoding="utf-8") as f:
        scheme = json.load(f)
    return scheme["house"]


def _call_external_api(image_path: str) -> dict:
    """调用外部户型识别服务（现成 API/SaaS）。返回归一化 house dict。

    TODO: 按所选服务商文档实现：
      - POST 图片到 RECOGNITION_API_URL，携带 RECOGNITION_API_KEY；
      - 解析响应：墙体线段 → walls（p1/p2/thickness/type），
        房间轮廓 → rooms，门窗 → openings，标注尺寸 → mm 比例校准；
      - 承重墙判定保守：不确定标 wall_type="suspect_load_bearing"。
    当前为占位，抛异常由调用方回退 Mock。
    """
    raise NotImplementedError("RECOGNITION_API_URL 接入口碑待实现（见 docs/floorplan_recognition_options.md）")


def recognize(image_path: str = None) -> dict:
    """MVP：优先外部识别，失败回退 Mock。始终写入 original_walls 基线。"""
    house = None
    api_url = os.environ.get("RECOGNITION_API_URL")
    if api_url and image_path:
        try:
            house = _call_external_api(image_path)
        except NotImplementedError:
            house = None
        except Exception:
            house = None  # 任何识别异常都安全回退
    if house is None:
        house = _mock_house()

    # 安全基线：记录初始墙体，供约束引擎检测"承重墙被移除"
    house["original_walls"] = [dict(w) for w in house["walls"]]
    return house


def apply_house(scheme: dict, house: dict) -> dict:
    scheme["house"] = house
    return scheme
