# Interior Design Agent（单人 + Agent 驱动启动包）

> 目标：上传户型图 → 说话/发图 → 一键生成可施工室内方案（3D + 尺寸 + 施工图 + 报价）→ 对话持续优化。
> 定位：单人团队，靠 AI agent 干活。人是架构师/产品经理/验收官，agent 是码农/算法/测试。

## 仓库结构

```
interior_design_agent/
├── README.md                 # 本文件
├── SOLO_ROADMAP.md           # B：单人 agent 时序任务清单
├── WEEK1_AGENT_PROMPTS.md    # C：第一周给 agent 的指令集（直接复制用）
├── home_agent_mvp/           # A：可运行项目脚手架
│   ├── app.py                # Flask 服务入口
│   ├── agents/               # 各 Agent 模块
│   │   ├── understand.py     # 户型识别（MVP 用 Mock，留接口）
│   │   ├── planner.py        # 规划 Agent（LLM 调用占位）
│   │   ├── generator.py      # 生成 Agent（可控构件拼装）
│   │   ├── constraint.py     # 约束引擎
│   │   └── dialog.py         # 对话 Agent（Function Calling 思路）
│   ├── data/
│   │   ├── scheme.json       # 单一数据骨架（方案 JSON）
│   │   ├── components.json   # 参数化构件库
│   │   └── constraints.yaml  # 约束规则库
│   ├── render/
│   │   └── mock_render.py    # Mock 渲染（真实接云渲染）
│   ├── engineering/
│   │   └── bom.py            # 算量/报价/出图（Mock）
│   ├── tests/                # pytest 单测
│   │   ├── test_constraint.py
│   │   └── test_dialog.py
│   ├── requirements.txt
│   └── run.sh                # 一键启动
└── docs/                     # 调研与方案文档（见下文"配套资料"）
```

## 快速开始

```bash
cd home_agent_mvp
pip install -r requirements.txt
bash run.sh
# 另开终端：
curl -X POST localhost:5000/generate -H "Content-Type: application/json" \
  -d '{"need":"现代简约 两口之家 多收纳"}'
curl -X POST localhost:5000/dialog -H "Content-Type: application/json" \
  -d '{"text":"主卧衣柜加长 30cm"}'
```

## 单人启动三步走

1. 先跑通 `home_agent_mvp`（阶段 A：骨架闭环）。
2. 替换 Mock：接真实 LLM API 做规划/对话，接开源户型识别做理解（阶段 B）。
3. 接云渲染 + 工程出图 + 小程序（阶段 C）。

详细时序见 `SOLO_ROADMAP.md`，第一周指令见 `WEEK1_AGENT_PROMPTS.md`。

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
