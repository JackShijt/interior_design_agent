# AI 室内设计 Agent —— MVP 补充文档

> 配套：AI室内设计Agent产品技术方案.md
> 内容：① MVP 详细 PRD  ② 约束规则库示例  ③ 技术原型 Demo 代码框架
> 时间：2026-07-14

---

# 第一部分：MVP 详细 PRD（产品需求文档）

## 1.1 产品概述

| 项 | 内容 |
|----|------|
| 产品名（暂定） | 户型老师 / HomeAgent MVP |
| 版本 | v0.1（MVP） |
| 目标 | 验证"上传户型图 → 说话生成可施工全套方案"核心价值 |
| 周期 | 4–6 个月 |
| 平台 | 微信小程序 + H5（先做移动端） |
| 核心链路 | 上传户型图 → 识别 → 一句话生成 → 3D+尺寸+图纸+报价 → 对话微调 |

## 1.2 用户故事（核心场景）

**US-1 上传户型图识别**
> 作为业主，我想拍/传户型图，系统自动识别墙门窗和尺寸，这样我不用自己画。
- 验收：识别准确率墙体≥90%、尺寸误差≤5%；提供手动校正。

**US-2 一句话生成方案**
> 作为小白，我说"现代简约、两口之家、多收纳"，系统给出 3D+尺寸+图纸+报价。
- 验收：10 秒内出首版；含 3D 效果、尺寸标注、平面布置图、报价单。

**US-3 对话微调**
> 我想说"主卧衣柜加长 30cm"，方案同步更新 3D/尺寸/报价。
- 验收：单次修改全链路刷新 < 3 秒；价格/尺寸变化可见。

**US-4 参考图换风格**
> 我发一张喜欢的图，系统把我家换成类似风格。
- 验收：色调/材质迁移到我家约束下，不照搬布局。

**US-5 导出交付包**
> 我想把方案导出给工长/自己买材料。
- 验收：导出 PDF（效果+尺寸+图纸+报价）和水电点位图。

## 1.3 功能需求清单（FR）

### FR-1 户型图上传与识别
- FR-1.1 支持拍照/相册/CAD 图片上传
- FR-1.2 自动识别：外墙、内墙、门、窗、房间名、尺寸标注
- FR-1.3 标记"疑似承重墙"（保守策略，禁止 AI 拆改）
- FR-1.4 手动校正：拖动点/线、改尺寸、标承重
- FR-1.5 比例校准：用标注尺寸反推毫米比例

### FR-2 需求采集
- FR-2.1 文本输入（自然语言）
- FR-2.2 结构化快捷选项（风格/家庭结构/预算/重点需求）
- FR-2.3 参考图上传（风格提取）

### FR-3 方案生成
- FR-3.1 规划 Agent：空间功能分配
- FR-3.2 生成 Agent（路线 A 构件拼装）：家具/硬装布局
- FR-3.3 约束引擎前置校验
- FR-3.4 输出 design JSON

### FR-4 结果呈现
- FR-4.1 3D 效果（云渲染，可旋转/720°）
- FR-4.2 尺寸标注（墙、家具）
- FR-4.3 平面布置图（2D）
- FR-4.4 物料清单 + 报价单（分房间）
- FR-4.5 合规性提示（风险提示）

### FR-5 对话优化
- FR-5.1 自然语言解析 → Function Call
- FR-5.2 尺寸/位置/数量修改
- FR-5.3 风格切换（含参考图）
- FR-5.4 冲突协商（给替代方案）
- FR-5.5 撤销/重做（方案快照）

### FR-6 导出
- FR-6.1 导出 PDF 交付包
- FR-6.2 导出水电点位图（基础）
- FR-6.3 分享链接

## 1.4 非功能需求（NFR）

| 类别 | 要求 |
|------|------|
| 性能 | 首版生成 < 10s；对话修改全链路 < 3s |
| 精度 | 墙体识别 ≥90%；尺寸误差 ≤5% |
| 安全 | 户型图本地脱敏；不留存原始人脸 |
| 合规 | 承重墙改动强制人工确认 + 免责声明 |
| 可用性 | 小白 3 步内出首版，无需教程 |
| 成本 | 单次生成云渲染成本可控（GPU 虚拟化） |

## 1.5 边界（MVP 不做）
- 自由生成式 3D（路线 B）
- 复杂水电深化、暖通
- AR 实景、VR 沉浸
- 施工派单、电商交易闭环
- 多城规范全量适配

## 1.6 关键指标（成功标准）
- 首版生成成功率 ≥ 85%
- 用户 3 步内出图占比 ≥ 70%
- 对话修改采纳率 ≥ 60%
- 单用户平均对话轮次 ≥ 4（说明真在用对话迭代）

---

# 第二部分：约束规则库示例

## 2.1 规则文件格式（YAML DSL）

```yaml
# constraints/v1/base.yaml
version: 1.0
scope: china_residential_general   # 可扩展分城市

rules:
  # ---------- A 类：结构安全（红线，阻断） ----------
  - id: A001
    category: structural_safety
    level: block
    name: 承重墙禁止拆除
    condition:
      action: remove_wall
      wall_type: bearing
    action:
      type: block
      message: "承重墙不可拆除，存在安全隐患。如需空间连通，建议采用垭口/半墙替代。"
    source: "建筑结构荷载规范 GB50009"

  - id: A002
    category: structural_safety
    level: block
    name: 承重墙禁止开大洞
    condition:
      action: open_hole
      wall_type: bearing
      width_gt: 1200
    action:
      type: block
      message: "承重墙开洞宽度不得超过 1200mm，且需结构加固。"
    source: "GB50009"

  - id: A003
    category: structural_safety
    level: block
    name: 管井禁止移位
    condition:
      action: move
      element: [pipe_shaft, flue]
    action:
      type: block
      message: "管井/烟道位置不可移动。"

  # ---------- B 类：规范合规（强提示，需确认） ----------
  - id: B001
    category: code_compliance
    level: warn_confirm
    name: 卫生间防水范围
    condition:
      action: set_material
      room_type: bathroom
      material_not_in: [waterproof_coating]
    action:
      type: warn
      message: "卫生间墙面/地面必须使用防水涂层，建议涂刷高度≥1800mm。"

  - id: B002
    category: code_compliance
    level: warn_confirm
    name: 插座高度
    condition:
      action: place_socket
      height_lt: 300
    action:
      type: warn
      message: "普通插座距地宜 300mm，低于此需确认。"

  # ---------- C 类：人体工学（软约束，优化目标） ----------
  - id: C001
    category: ergonomics
    level: optimize
    name: 主通道宽度
    condition:
      corridor_width_lt: 900
    action:
      type: optimize
      message: "主要通道建议≥900mm，当前过窄。"

  - id: C002
    category: ergonomics
    level: optimize
    name: 衣柜深度
    condition:
      furniture: wardrobe
      depth_not_in: [550, 600]
    action:
      type: optimize
      message: "衣柜深度建议 550–600mm。"

  - id: C003
    category: ergonomics
    level: optimize
    name: 床侧通道
    condition:
      furniture: bed
      side_clearance_lt: 500
    action:
      type: optimize
      message: "床侧需预留≥500mm 通行/取物空间。"

  # ---------- D 类：工艺可行（生成时校验） ----------
  - id: D001
    category: craft
    level: warn
    name: 瓷砖模数
    condition:
      action: tile_layout
      not_modulus: 300
    action:
      type: warn
      message: "瓷砖排布建议按 300mm 模数，减少裁切损耗。"
```

## 2.2 规则执行伪代码

```python
def evaluate(scheme_json, rules):
    report = {"block": [], "warn": [], "optimize": []}
    for rule in rules:
        if matches(rule.condition, scheme_json):
            report[rule.level].append(rule.action.message)
            if rule.level == "block":
                return Reject(report)        # 阻断，不改 JSON
    return Accept(report)                     # 通过，提交变更
```

## 2.3 规则库运营
- 热更新：YAML 改完即生效，无需发版。
- 分城市/分规范：scope 字段控制加载哪套。
- 数据沉淀：用户手动校正 → 反哺规则/识别模型。

---

# 第三部分：技术原型 Demo 代码框架

> 目标：用一个最小可运行原型（Python + Flask + 简单规则引擎 + Mock 渲染）跑通
> "户型 JSON → 约束校验 → 对话修改 → 输出方案" 的核心闭环，验证架构可行性。

## 3.1 目录结构

```
home_agent_mvp/
├── app.py                 # Flask 服务入口
├── agents/
│   ├── understand.py      # 户型识别（此处 Mock，真实接 CV）
│   ├── planner.py         # 规划 Agent（LLM 调用）
│   ├── generator.py       # 生成 Agent（构件拼装）
│   ├── constraint.py      # 约束引擎
│   └── dialog.py          # 对话 Agent（Function Calling）
├── data/
│   ├── scheme.json        # 单一数据骨架（方案 JSON）
│   ├── components.json    # 参数化构件库
│   └── constraints.yaml   # 约束规则库
├── render/
│   └── mock_render.py     # Mock 渲染（真实接 KooEngine 类）
├── engineering/
│   └── bom.py             # 算量/报价/出图（Mock）
└── requirements.txt
```

## 3.2 单一数据骨架：scheme.json（示例）

```json
{
  "project_id": "demo_001",
  "unit": "mm",
  "house": {
    "walls": [
      {"id":"w1","p1":[0,0],"p2":[4200,0],"thickness":200,"type":"bearing","height":2800},
      {"id":"w2","p1":[4200,0],"p2":[4200,3600],"thickness":200,"type":"partition","height":2800}
    ],
    "openings": [
      {"id":"d1","wall_id":"w1","type":"door","offset":1200,"width":900,"height":2100}
    ],
    "rooms": [
      {"id":"r1","name":"主卧","type":"bedroom","poly":[[0,0],[4200,0],[4200,3600],[0,3600]],"area":15.12}
    ],
    "fixed": [{"type":"pipe_shaft","poly":[[4000,3400],[4200,3400],[4200,3600],[4000,3600]]}]
  },
  "design": {
    "style": "modern_minimal",
    "furniture": [
      {"id":"f1","cat":"wardrobe","model":"wd_01","pos":[100,200],"size":[1800,600,2400],"price":3200}
    ]
  },
  "engineering": {"bom": [], "quotation": {}, "drawings": []}
}
```

## 3.3 约束引擎：constraint.py

```python
import yaml

def load_rules(path="data/constraints.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]

def _matches(cond, scheme):
    """极简条件匹配（真实系统用规则引擎 DSL 解析）"""
    # 示例：检测"拆承重墙"
    if cond.get("action") == "remove_wall":
        for w in scheme["house"]["walls"]:
            if w["id"] == cond.get("wall_id") and w["type"] == "bearing":
                return True
    return False

def evaluate(scheme, rules):
    report = {"block": [], "warn": [], "optimize": []}
    for rule in rules:
        if _matches(rule["condition"], scheme):
            lvl = rule["level"]
            if lvl == "block":
                report["block"].append(rule["action"]["message"])
            elif lvl == "warn_confirm":
                report["warn"].append(rule["action"]["message"])
            else:
                report["optimize"].append(rule["action"]["message"])
    if report["block"]:
        return False, report
    return True, report
```

## 3.4 生成 Agent（构件拼装）：generator.py

```python
import json

def generate(scheme, user_need: str):
    """MVP：基于规则从构件库拼装（真实接 LLM 规划）"""
    components = json.load(open("data/components.json", encoding="utf-8"))
    # 简化：主卧放一个衣柜（模型 wd_01）
    scheme["design"]["furniture"].append({
        "id": "f_auto_1",
        "cat": "wardrobe",
        "model": "wd_01",
        "pos": [100, 200],
        "size": [1800, 600, 2400],
        "price": 3200
    })
    scheme["design"]["style"] = "modern_minimal"
    return scheme
```

## 3.5 对话 Agent（Function Calling 思路）：dialog.py

```python
import json, re

def handle_command(scheme, text: str):
    """解析自然语言 → 结构化编辑（MVP 用正则，真实用 LLM Function Calling）"""
    # 例："主卧衣柜加长 30cm"
    m = re.search(r"加长\s*(\d+)\s*cm", text)
    if m and "衣柜" in text:
        delta = int(m.group(1)) * 10  # cm → mm
        for f in scheme["design"]["furniture"]:
            if f["cat"] == "wardrobe":
                f["size"][0] += delta
                f["price"] += delta // 100 * 150  # 简化计价
        return scheme, "已将衣柜加长 {}mm，价格更新。".format(delta)
    return scheme, "暂未理解该指令（MVP 仅支持尺寸修改示例）。"
```

## 3.6 工程 Agent（算量/报价）：engineering/bom.py

```python
def calc_bom(scheme):
    bom = []
    for f in scheme["design"]["furniture"]:
        bom.append({
            "name": f["cat"],
            "model": f["model"],
            "size": f["size"],
            "price": f["price"]
        })
    total = sum(b["price"] for b in bom)
    scheme["engineering"]["bom"] = bom
    scheme["engineering"]["quotation"] = {"total": total, "currency": "CNY"}
    return scheme
```

## 3.7 服务入口：app.py

```python
from flask import Flask, request, jsonify
import json
from agents import constraint, generator, dialog
from engineering import bom as eng

app = Flask(__name__)
scheme = json.load(open("data/scheme.json", encoding="utf-8"))
rules = constraint.load_rules()

@app.post("/generate")
def generate():
    global scheme
    need = request.json.get("need", "")
    scheme = generator.generate(scheme, need)
    ok, report = constraint.evaluate(scheme, rules)
    if not ok:
        return jsonify({"error": "约束阻断", "report": report}), 400
    scheme = eng.calc_bom(scheme)
    return jsonify({"scheme": scheme, "report": report})

@app.post("/dialog")
def talk():
    global scheme
    text = request.json.get("text", "")
    scheme, msg = dialog.handle_command(scheme, text)
    ok, report = constraint.evaluate(scheme, rules)
    if not ok:
        return jsonify({"error": "修改违反约束", "report": report}), 400
    scheme = eng.calc_bom(scheme)
    return jsonify({"message": msg, "scheme": scheme})

if __name__ == "__main__":
    app.run(debug=True)
```

## 3.8 运行与验证

```bash
pip install flask pyyaml
python app.py
# 终端 1
curl -X POST localhost:5000/generate -H "Content-Type: application/json" \
  -d '{"need":"现代简约两口之家多收纳"}'
# 终端 2（对话微调）
curl -X POST localhost:5000/dialog -H "Content-Type: application/json" \
  -d '{"text":"主卧衣柜加长 30cm"}'
```

验证点：
- 生成返回完整 scheme（含 design + engineering）。
- 对话修改后尺寸/价格变化，且约束校验通过。
- 若尝试"拆除承重墙"，约束引擎返回 block（演示红线守门）。

## 3.9 原型到生产的演进路径

| 原型组件 | MVP 真实替代 |
|----------|--------------|
| understand.py（Mock） | CVPR2021 类 CV 识别模型 |
| planner.py（占位） | LLM 空间规划推理 |
| generator.py（规则） | LLM + 约束优化生成 |
| dialog.py（正则） | LLM Function Calling |
| mock_render.py | KooEngine 类云渲染 |
| bom.py（简化） | 真实 BOM/报价/施工图引擎 |
| scheme.json（单文件） | 数据库 + 对象存储 + 版本管理 |

---

# 总结

本补充文档提供：
1. **MVP PRD**：用户故事、功能/非功能需求、边界、成功指标。
2. **约束规则库示例**：YAML DSL + 4 类规则（结构/规范/人体工学/工艺）+ 执行逻辑。
3. **技术原型 Demo**：可运行的 Flask 闭环（识别→生成→约束→对话→算量），并标注原型到生产的演进路径。

三者结合，可直接用于：团队立项评估、研发排期、技术原型 PoC 验证。
