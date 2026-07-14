# 第一周给 Agent 的指令集（C，直接复制用）

> 使用说明：你（人）把这些 prompt 复制给 coding agent（如 CodeBuddy / Cursor / Claude）。
> 每条都带"范围 + 验收"，agent 交差后你只判卷。
> 前提：仓库已 clone，路径 `interior_design_agent/home_agent_mvp/`，Python 用 `python3 -m venv .venv` 建虚拟环境。

---

## Prompt 1：环境跑通（第 1 天）

```
在 interior_design_agent/home_agent_mvp/ 目录下：
1. 用 `python3 -m venv .venv` 建虚拟环境并激活；
2. `pip install -r requirements.txt`；
3. 运行 `python -m pytest tests/ -q`，必须 6 passed；
4. 运行 `bash run.sh` 启动 Flask，另开终端执行：
   curl -X POST http://127.0.0.1:5000/generate -H "Content-Type: application/json" -d '{"need":"现代简约 两口之家 多收纳"}'
   curl -X POST http://127.0.0.1:5000/dialog -H "Content-Type: application/json" -d '{"text":"主卧衣柜加长 30cm"}'
   确认返回 200 且 JSON 正常。
注意：本地 5000 端口可能被 Apple AirTunes 占用，curl 必须用 http://127.0.0.1:5000 而非 localhost。
交付：把运行结果贴回，并说明每条命令的输出。
```

---

## Prompt 2：读懂数据流（第 1–2 天，调研型）

```
阅读 interior_design_agent/home_agent_mvp/ 下的代码：app.py、agents/*.py、engineering/bom.py、render/mock_render.py、data/*.json|yaml。
画一张"请求从 /generate 到返回"的数据流图（文字版即可），标出每个模块的职责与调用的函数。
重点说明：scheme.json 是如何被各模块读写的？约束引擎在哪一步介入？对话修改如何反映到 quotation？
交付：一份不超过 400 字的数据流说明 + 你发现的 3 个潜在改进点。
```

---

## Prompt 3：补全单测（第 2 天）

```
在 interior_design_agent/home_agent_mvp/tests/ 下为以下场景补 pytest 用例（新建 test_generator.py、test_bom.py）：
1. generator.generate 对"多收纳"需求能追加 wardrobe；
2. generator.generate 对空需求至少追加 1 件家具；
3. bom.calc_bom 计算 total = 各家具 price 之和；
4. constraint.evaluate 对"衣柜深度 500"（越界）应产生 optimize 提示；
5. dialog.handle_command 对"换成暖色调"应把 style 改为 warm。
运行 pytest 必须全绿。交付：新测试文件 + 运行结果。
```

---

## Prompt 4：规划 Agent 接真 LLM（第 3–4 天，需你提供 API Key）

```
把 interior_design_agent/home_agent_mvp/agents/planner.py 的占位实现替换为真实 LLM 调用（默认用 OpenAI 兼容接口，模型由环境变量 MODEL_NAME 指定；API Key 从环境变量 LLM_API_KEY 读取，不要硬编码）。
函数签名保持 plan(scheme, user_need) -> dict 不变。
功能：调用 LLM，把 user_need（如"现代简约 两口之家 多收纳"）解析为结构化策略：
  {"rooms":[{"type":"bedroom","functions":[...]}], "furniture_draft":[{"cat":"wardrobe","qty":1}], "style":"modern_minimal"}
LLM 只做语义推理，不要让它编造具体毫米尺寸。
加一个 plan_with_mock() 作为无 Key 时的降级（返回当前占位逻辑）。
写 test_planner.py：无 Key 时走 mock 返回合理结构；有 Key 时（你后续提供）走真实调用。
交付：修改后的 planner.py + 测试 + 运行结果。注意：不要提交任何密钥。
```

---

## Prompt 5：户型识别接开源方案（第 3–4 天，调研+实现）

```
调研并给出 interior_design_agent 项目"户型图识别"的可行方案（不超过 300 字）：
- 对比：(a) 调用现成 API/SaaS (b) 用开源模型 FloorSG / 类似 (c) 自研 CV。
- 给出 MVP 推荐与理由（考虑单人团队、成本、精度）。
保持 understand.recognize(image_path) -> house dict 的接口不变，给出推荐方案的接入骨架代码（可先留 TODO）。
交付：方案对比文档（写入 docs/ 或直接回复）+ recognize 的接入骨架（含清晰 TODO 注释）。不要实际训练模型。
```

---

## 你（人）的判卷清单（每周末花 30 分钟）

- [ ] agent 交付物是否通过 pytest 全绿？
- [ ] 是否误提交密钥 / 硬编码？（grep -rn "sk-" / "api_key" 自查）
- [ ] 是否改动了 scheme.json 的数据骨架契约？（动了要同步更新 README 结构说明）
- [ ] LLM 是否只做推理、没编造尺寸？（看 generator/planner 输出）
- [ ] 约束引擎是否仍在 generate/dialog 必经路径上？

> 判卷不过就打回 agent 重做，不要自己下手改——保持"你判卷、agent 干活"的分工。
