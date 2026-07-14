"""第 11 周：对话同步 + 快照/撤销单测（Flask test client）。"""
import os
import json
import tempfile

BASE = os.path.join(os.path.dirname(__file__), "..")


def _setup(tmp_path):
    import app as flask_app
    scheme_file = tmp_path / "scheme.json"
    versions_file = tmp_path / "versions.json"
    # 复制基础 scheme
    base = json.load(open(os.path.join(BASE, "data", "scheme.json"), encoding="utf-8"))
    scheme_file.write_text(json.dumps(base), encoding="utf-8")
    flask_app.BASE = str(tmp_path)
    flask_app.SCHEME_PATH = str(scheme_file)
    flask_app.VERSIONS_PATH = str(versions_file)
    return flask_app.app.test_client(), scheme_file


def test_dialog_syncs_render_scene(tmp_path):
    """对话改衣柜尺寸 → /render_scene 场景同步更新。"""
    import app as flask_app
    client, sf = _setup(tmp_path)
    # 先 generate
    client.post("/generate", json={"need": "现代简约 两口之家 多收纳"})
    before = client.get("/render_scene").get_json()
    w_before = [f["size"] for f in before["furniture"] if f["cat"] == "wardrobe"][0][0]
    # 对话加长 30cm
    client.post("/dialog", json={"text": "主卧衣柜加长 30cm"})
    after = client.get("/render_scene").get_json()
    w_after = [f["size"] for f in after["furniture"] if f["cat"] == "wardrobe"][0][0]
    assert w_after == w_before + 300


def test_snapshot_and_undo(tmp_path):
    """快照后对话修改，撤销可回到快照前状态。"""
    import app as flask_app
    client, sf = _setup(tmp_path)
    client.post("/generate", json={"need": "多收纳"})
    # 快照
    r = client.post("/snapshot")
    assert r.get_json()["status"] == "saved"
    # 修改
    client.post("/dialog", json={"text": "主卧衣柜加长 30cm"})
    modified = client.get("/render_scene").get_json()
    w_mod = [f["size"] for f in modified["furniture"] if f["cat"] == "wardrobe"][0][0]
    # 撤销
    r2 = client.post("/undo")
    assert r2.get_json()["status"] == "undone"
    restored = client.get("/render_scene").get_json()
    w_res = [f["size"] for f in restored["furniture"] if f["cat"] == "wardrobe"][0][0]
    assert w_res == w_mod - 300


def test_session_context_reference_across_requests(tmp_path):
    """同一 session_id 下，第二轮'再大点'应延续上一轮衣柜尺寸（跨 HTTP 请求记忆）。"""
    import app as flask_app
    client, sf = _setup(tmp_path)
    client.post("/generate", json={"need": "现代简约 多收纳"})
    # 第一轮：明确对象
    client.post("/dialog", json={"text": "主卧衣柜加长 30cm", "session_id": "ctx_sess"})
    after1 = client.get("/render_scene").get_json()
    w1 = [f["size"] for f in after1["furniture"] if f["cat"] == "wardrobe"][0][0]
    # 第二轮：指代延续（不重复说"衣柜"）
    r2 = client.post("/dialog", json={"text": "再大点", "session_id": "ctx_sess"})
    assert r2.status_code == 200
    after2 = client.get("/render_scene").get_json()
    w2 = [f["size"] for f in after2["furniture"] if f["cat"] == "wardrobe"][0][0]
    assert w2 == w1 + 100  # 默认 +100mm 指代延续
    # 不同 session 不应串上下文
    r3 = client.post("/dialog", json={"text": "再大点", "session_id": "other_sess"})
    # other_sess 无历史 → 无法指代，返回未理解（不崩溃）
    assert "暂未理解" in r3.get_json()["message"] or "衣柜" in r3.get_json()["message"]
