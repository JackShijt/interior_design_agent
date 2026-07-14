"""HomeAgent MVP 服务入口：跑通 识别→规划→生成→约束→工程→对话 闭环。"""
import json
import os
from flask import Flask, request, jsonify

from agents import constraint, generator, dialog, understand, planner
from engineering import bom as eng
from engineering import export_pdf as exporter
from render import mock_render as render
from render import scene as scene_render

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "frontend"))

BASE = os.path.dirname(__file__)
SCHEME_PATH = os.path.join(BASE, "data", "scheme.json")
_rules = constraint.load_rules()


def _load_scheme() -> dict:
    with open(SCHEME_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_scheme(scheme: dict):
    with open(SCHEME_PATH, "w", encoding="utf-8") as f:
        json.dump(scheme, f, ensure_ascii=False, indent=2)


def _push_snapshot():
    """把当前 scheme 追加到历史版本栈（供撤销）。"""
    import datetime
    versions = []
    if os.path.exists(VERSIONS_PATH):
        with open(VERSIONS_PATH, "r", encoding="utf-8") as f:
            versions = json.load(f)
    versions.append({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                     "scheme": _load_scheme()})
    with open(VERSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(versions[-20:], f, ensure_ascii=False, indent=2)


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
    _push_snapshot()                                  # 归档版本（供撤销）
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
    _push_snapshot()                                  # 归档版本（供撤销）
    _save_scheme(scheme)
    return jsonify({"message": msg, "scheme": scheme, "report": report})


@app.get("/health")
def api_health():
    return jsonify({"status": "ok"})


@app.get("/")
def api_index():
    return app.send_static_file("index.html")


@app.get("/render_scene")
def api_render_scene():
    """返回当前 scheme 的 Three.js 场景描述，供前端 3D 展示。"""
    scheme = _load_scheme()
    return jsonify(scene_render.to_scene(scheme))


VERSIONS_PATH = os.path.join(BASE, "data", "versions.json")


@app.post("/snapshot")
def api_snapshot():
    """保存当前方案为快照（用于撤销）。"""
    import datetime
    scheme = _load_scheme()
    versions = []
    if os.path.exists(VERSIONS_PATH):
        with open(VERSIONS_PATH, "r", encoding="utf-8") as f:
            versions = json.load(f)
    snap = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "scheme": scheme,
    }
    versions.append(snap)
    with open(VERSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(versions[-20:], f, ensure_ascii=False, indent=2)
    return jsonify({"status": "saved", "count": len(versions)})


@app.post("/undo")
def api_undo():
    """撤销到上一快照。"""
    if not os.path.exists(VERSIONS_PATH):
        return jsonify({"error": "无快照"}), 400
    with open(VERSIONS_PATH, "r", encoding="utf-8") as f:
        versions = json.load(f)
    if len(versions) < 2:
        return jsonify({"error": "无可撤销快照"}), 400
    versions.pop()  # 丢弃当前
    prev = versions[-1]["scheme"]
    _save_scheme(prev)
    with open(VERSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "undone", "scheme": prev})


@app.get("/export")
def api_export():
    """导出 PDF 交付包（效果+尺寸+图纸+报价）。返回文件路径。"""
    scheme = _load_scheme()
    path = os.path.join(BASE, "data", "delivery.pdf")
    out = exporter.export_pdf(scheme, path)
    return jsonify({"path": out, "total": scheme["engineering"].get("quotation", {}).get("total", 0)})


@app.post("/confirm_demolition")
def api_confirm_demolition():
    """红线人工确认：接收确认操作 + 确认人，记录审计日志，执行拆改。"""
    data = request.json or {}
    action = data.get("action")
    wall_type = data.get("wall_type")
    confirmed_by = data.get("confirmed_by", "anonymous")
    if action not in ("remove_wall", "open_hole"):
        return jsonify({"error": "无效操作"}), 400

    scheme = _load_scheme()
    # 校验该意图确实在 pending_actions 中（防止越权直接调用）
    intent = next((it for it in scheme.get("pending_actions", [])
                   if it.get("action") == action and it.get("wall_type") == wall_type), None)
    if intent is None:
        return jsonify({"error": "无对应待确认意图"}), 400

    # 仅当非承重墙，或承重墙已显式确认，才执行
    if wall_type == "bearing" and action == "remove_wall":
        # 承重墙拆除：即便确认也仅记录，不在 MVP 自动执行（安全保守）
        _audit(confirmed_by, action, wall_type, executed=False)
        return jsonify({"status": "recorded",
                        "message": "承重墙拆除已记录但需线下结构加固，MVP 不自动执行。"})
    # 非承重墙：执行（从 walls 移除对应类型墙，演示用移除首条）
    if action == "remove_wall":
        scheme["house"]["walls"] = [w for w in scheme["house"]["walls"]
                                    if w.get("type") != wall_type] or scheme["house"]["walls"]
        _audit(confirmed_by, action, wall_type, executed=True)
        # 清除已确认意图
        scheme["pending_actions"] = [it for it in scheme["pending_actions"]
                                     if not (it.get("action") == action and it.get("wall_type") == wall_type)]
        _save_scheme(scheme)
        return jsonify({"status": "executed", "message": f"{wall_type} 墙已拆除（已审计）"})
    # 开洞：MVP 仅记录
    _audit(confirmed_by, action, wall_type, executed=False)
    return jsonify({"status": "recorded", "message": "开洞申请已记录，需线下施工。"})


def _audit(who: str, action: str, wall_type: str, executed: bool):
    """写审计日志到 data/audit.log。"""
    import datetime
    log_path = os.path.join(BASE, "data", "audit.log")
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"{ts} | who={who} | action={action} | wall_type={wall_type} | executed={executed}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


if __name__ == "__main__":
    # 注意：macOS 上 5000 端口常被 AirPlay Receiver 占用，默认改用 5001 并绑定 127.0.0.1
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5001)))
