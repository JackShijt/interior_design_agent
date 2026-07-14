"""第 8 周：安全红线单测。"""
import os
import json
import tempfile

BASE = os.path.join(os.path.dirname(__file__), "..")


def _scheme_with_bearing():
    return {
        "design": {"style": "modern_minimal", "furniture": []},
        "house": {
            "walls": [
                {"id": "w1", "type": "bearing", "p1": [0, 0], "p2": [100, 0]},
                {"id": "w2", "type": "partition", "p1": [0, 0], "p2": [0, 100]},
            ],
            "original_walls": [
                {"id": "w1", "type": "bearing"}, {"id": "w2", "type": "partition"},
            ],
            "rooms": [],
        },
        "pending_actions": [],
    }


def test_remove_bearing_blocked():
    """拆承重墙意图 → 约束阻断。"""
    from agents import constraint
    s = _scheme_with_bearing()
    s["pending_actions"] = [{"action": "remove_wall", "wall_type": "bearing"}]
    ok, report = constraint.evaluate(s, constraint.load_rules())
    assert ok is False
    assert any("承重墙" in m for m in report["block"])


def test_bearing_demolition_not_auto_executed():
    """承重墙拆除被约束直接阻断，返回替代方案，且意图被记录。"""
    from agents import dialog
    s = _scheme_with_bearing()
    os.environ.pop("LLM_API_KEY", None)
    s, msg = dialog.dialog_with_mock(s, "拆掉承重墙")
    # 红线生效：被阻断并返回替代方案
    assert "承重墙不可拆除" in msg
    # 意图仍记录在 pending_actions，供审计/确认展示
    assert any(it.get("action") == "remove_wall" and it.get("wall_type") == "bearing"
               for it in s["pending_actions"])


def test_confirm_partition_via_flask_client(tmp_path):
    """确认拆非承重墙 → 执行且审计有记录（Flask test client）。"""
    import app as flask_app

    audit_log = tmp_path / "audit.log"
    scheme_file = tmp_path / "scheme_test.json"
    s = _scheme_with_bearing()
    s["pending_actions"] = [{"action": "remove_wall", "wall_type": "partition"}]
    scheme_file.write_text(json.dumps(s), encoding="utf-8")

    # 重定向 BASE 与审计路径到临时目录
    flask_app.BASE = str(tmp_path)
    flask_app._audit = lambda who, action, wall_type, executed: audit_log.write_text(
        f"{who}|{action}|{wall_type}|{executed}\n", encoding="utf-8")
    flask_app.SCHEME_PATH = str(scheme_file)

    client = flask_app.app.test_client()
    resp = client.post("/confirm_demolition",
                       json={"action": "remove_wall", "wall_type": "partition",
                             "confirmed_by": "owner"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "executed"
    # 审计已写
    assert "partition" in audit_log.read_text(encoding="utf-8")
    # scheme 中 pending_actions 已清除
    updated = json.loads(scheme_file.read_text(encoding="utf-8"))
    assert not any(it.get("action") == "remove_wall" and it.get("wall_type") == "partition"
                   for it in updated["pending_actions"])
