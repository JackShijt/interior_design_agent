"""第 4 周：understand.recognize 单测（走 Mock 回退路径，断言结构完整）。"""
import os
from agents import understand


def test_recognize_mock_has_walls_and_rooms():
    """Mock 回退：墙体数>0 且含 rooms。"""
    os.environ.pop("RECOGNITION_API_URL", None)
    house = understand.recognize()
    assert len(house.get("walls", [])) > 0
    assert len(house.get("rooms", [])) > 0


def test_recognize_writes_original_walls_baseline():
    """recognize 必须写入 original_walls 基线，供约束引擎比对。"""
    os.environ.pop("RECOGNITION_API_URL", None)
    house = understand.recognize()
    assert "original_walls" in house
    assert len(house["original_walls"]) == len(house["walls"])
    # 基线内容与当前墙体一致（未改动时）
    assert house["original_walls"][0]["id"] == house["walls"][0]["id"]


def test_recognize_falls_back_when_api_configured_but_unimplemented():
    """配置 API 但未实现时，安全回退 Mock，不崩溃。"""
    os.environ["RECOGNITION_API_URL"] = "http://fake.example.com/recognize"
    house = understand.recognize("fake.png")
    assert len(house.get("walls", [])) > 0
    os.environ.pop("RECOGNITION_API_URL", None)
