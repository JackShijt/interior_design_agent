"""HomeAgent MVP 服务入口：跑通 识别→规划→生成→约束→工程→对话 闭环。"""
import json
import os
from flask import Flask, request, jsonify

from agents import constraint, generator, dialog, understand, planner
from engineering import bom as eng
from render import mock_render as render

app = Flask(__name__)

BASE = os.path.dirname(__file__)
SCHEME_PATH = os.path.join(BASE, "data", "scheme.json")
_rules = constraint.load_rules()


def _load_scheme() -> dict:
    with open(SCHEME_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_scheme(scheme: dict):
    with open(SCHEME_PATH, "w", encoding="utf-8") as f:
        json.dump(scheme, f, ensure_ascii=False, indent=2)


@app.post("/generate")
def api_generate():
    scheme = _load_scheme()
    need = request.json.get("need", "")
    scheme["house"] = understand.recognize()          # MVP: Mock 户型
    scheme["design"] = {"style": "modern_minimal", "furniture": []}  # 重置设计，避免累积
    scheme["pending_actions"] = []                    # 重置安全意图
    planner.plan(scheme, need)                        # 规划（占位）
    scheme = generator.generate(scheme, need)         # 生成（构件拼装）
    ok, report = constraint.evaluate(scheme, _rules)  # 约束校验
    if not ok:
        return jsonify({"error": "约束阻断", "report": report}), 400
    scheme = eng.calc_bom(scheme)                     # 算量报价
    render.render(scheme)                             # 渲染（Mock）
    _save_scheme(scheme)
    return jsonify({"scheme": scheme, "report": report})


@app.post("/dialog")
def api_dialog():
    scheme = _load_scheme()
    text = request.json.get("text", "")
    scheme, msg = dialog.handle_command(scheme, text)  # 对话修改
    ok, report = constraint.evaluate(scheme, _rules)   # 约束校验
    if not ok:
        return jsonify({"error": "修改违反约束", "report": report,
                        "message": msg}), 400
    scheme = eng.calc_bom(scheme)
    render.render(scheme)
    _save_scheme(scheme)
    return jsonify({"message": msg, "scheme": scheme, "report": report})


@app.get("/health")
def api_health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
