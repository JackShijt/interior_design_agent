# Interior Design Agent（单人 + Agent 驱动启动包）

> 目标：上传户型图 → 说话/发图 → 一键生成可施工室内方案（3D + 尺寸 + 施工图 + 报价）→ 对话持续优化。
> 定位：单人团队，靠 AI agent 干活。人是架构师/产品经理/验收官，agent 是码农/算法/测试。

## 仓库结构

```
interior_design_agent/
├── README.md                 # 本文件
├── SOLO_ROADMAP.md           # B：单人 agent 时序任务清单
├── WEEK1_AGENT_PROMPTS.md    # C：第一周给 agent 的指令集（直接复制用）
├── WEEKLY_TASKS.md           # 逐周任务卡（直接让 agent 按周执行）
├── home_agent_mvp/           # A：可运行项目脚手架
│   ├── app.py                # Flask 服务入口（含 /generate /dialog /render_scene /export /snapshot /undo /confirm_demolition）
│   ├── agents/               # 各 Agent 模块
│   │   ├── understand.py     # 户型识别（MVP Mock，留外部 API 接入骨架）
│   │   ├── planner.py        # 规划 Agent（LLM 调用，无 Key 降级）
│   │   ├── generator.py      # 生成 Agent（按风格筛选构件拼装）
│   │   ├── constraint.py     # 约束引擎（承重墙/防水/通道等红线）
│   │   └── dialog.py         # 对话 Agent（LLM Function Calling，无 Key 降级）
│   ├── data/
│   │   ├── scheme.json       # 单一数据骨架（方案 JSON）
│   │   ├── components.json   # 参数化构件库（33 件，含 BOM 模板+单价）
│   │   ├── constraints.yaml  # 约束规则库
│   │   └── versions.json     # 方案快照（撤销用，运行时生成）
│   ├── render/
│   │   ├── mock_render.py    # Mock 渲染
│   │   └── scene.py          # scheme → Three.js 场景描述
│   ├── engineering/
│   │   ├── bom.py            # 算量/报价（分项明细）
│   │   └── export_pdf.py     # PDF 交付包（纯标准库生成）
│   ├── frontend/
│   │   └── index.html        # Three.js 3D Viewer + 对话/快照/撤销 UI
│   ├── tests/                # pytest 单测（35 用例）
│   ├── requirements.txt
│   └── run.sh                # 一键启动（端口 5001）
└── docs/                     # 调研与方案文档
    ├── compliance.md         # 合规文案与隐私脱敏
    ├── known_limitations.md  # 已知限制清单
    └── floorplan_recognition_options.md  # 户型识别选型
```

## 快速开始

```bash
cd home_agent_mvp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash run.sh            # 默认 http://127.0.0.1:5001
```

打开浏览器访问 http://127.0.0.1:5001 ：可一键生成、3D 旋转查看、对话框改方案、快照/撤销、导出 PDF。

API 调试（命令行）：
```bash
curl -X POST http://127.0.0.1:5001/generate -H "Content-Type: application/json" \
  -d '{"need":"现代简约 两口之家 多收纳"}'
curl -X POST http://127.0.0.1:5001/dialog -H "Content-Type: application/json" \
  -d '{"text":"主卧衣柜加长 30cm"}'
curl -X POST http://127.0.0.1:5001/export
```

### 接入真实 LLM / 识别（可选，环境变量注入，不硬编码）
```bash
export LLM_API_KEY="你的Key"
export MODEL_NAME="gpt-4o-mini"          # 或 deepseek-chat
export LLM_BASE_URL="https://api.deepseek.com/v1"   # 兼容 OpenAI 接口
export RECOGNITION_API_URL="https://xxx/recognize"  # 户型识别服务（待实现 _call_external_api）
```
不设置时，planner/dialog 自动走规则降级，识别走内置 Mock 户型。

## 单人启动三步走

1. 先跑通 `home_agent_mvp`（第 1–2 周：骨架闭环 + 单测）。
2. 按 `WEEKLY_TASKS.md` 逐周让 agent 推进（第 3–11 周：真 LLM/识别、构件库、渲染、出图、对话同步）。
3. 第 12 周：真实用户测试 + 合规上线。

详细逐周指令见 `WEEKLY_TASKS.md`。

## 配套资料（调研与方案文档）

位于 `docs/` 目录：

- `3D建模软件调研清单.md`
- `室内设计软件调研清单.md`
- `AI与云渲染技术深度拆解.md`
- `AI室内设计Agent产品技术方案.md`
- `AI室内设计Agent_MVP补充文档.md`
- `AI室内设计Agent_功能与技术难点拆解.md`
- `AI室内设计Agent_研发任务拆分.md`

单人落地指南：

- `SOLO_ROADMAP.md`：单人 + Agent 驱动的任务时序
- `WEEK1_AGENT_PROMPTS.md`：第一周给 Agent 的指令集（直接复制）

## 核心设计原则

**单一数据骨架**：所有下游（3D 渲染、施工图、报价、对话修改）由同一份 `scheme.json` 驱动。改 JSON 一处，全视图重算。
**P0 生死线**：承重墙判定、合规安全、全链路同步必须最先做且不可妥协。
**MVP 用可控构件拼装**，不碰自由生成式 3D，降低不可控风险。
**LLM 只做推理，数值全走规则引擎/BOM**，避免幻觉编造尺寸价格。
**安全红线**：拆承重墙 100% 阻断或强制人工确认，审计可追溯（`data/audit.log`）。

## 合规与隐私

- 户型图在本地/授权环境处理，不上传第三方（详见 `docs/compliance.md`）；
- AI 生成方案仅供参考，施工前须专业工程师复核；
- 不收集用户敏感信息，密钥仅经环境变量注入，禁止硬编码。

## 测试

```bash
cd home_agent_mvp && source .venv/bin/activate
python -m pytest tests/ -q    # 35 passed
```
