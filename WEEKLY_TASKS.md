# 逐周任务卡（单人 + Agent 驱动）

> 用法：每周你只做三件事——
> 1. 把当周「Agent 指令」复制给 coding agent（CodeBuddy / Cursor / Claude）；
> 2. agent 交差后，按当周「验收清单」判卷；
> 3. 打回重做 or 通过，进入下一周。
>
> 原则（贯穿全程）：
> - 单一数据骨架 `scheme.json` 是轴心，所有模块读写它；
> - 约束引擎 `constraint.evaluate` 必须在 `generate` / `dialog` 必经路径上；
> - LLM 只做语义推理，禁止编造毫米尺寸；
> - 承重墙/安全红线最终口径由你拍板，agent 只建议；
> - 绝不提交密钥（环境变量 `LLM_API_KEY` / `MODEL_NAME` 注入，不硬编码）。
>
> 路径约定：所有任务根目录为 `interior_design_agent/home_agent_mvp/`，Python 用 `python3 -m venv .venv` 建虚拟环境，命令前先 `source .venv/bin/activate`。
> 端口注意：本地 5000 端口可能被 Apple AirTunes 占用，curl 一律用 `http://127.0.0.1:5000` 而非 `localhost`。

---

## 第 1 周：骨架闭环跑通 + 读懂代码

**目标**：本地能跑通 `generate → 约束 → 对话 → 算量` 闭环，你理解数据流。

**Agent 指令（复制给 agent）：**
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

**验收清单（你判卷）：**
- [ ] `pytest` 6 passed；
- [ ] 两条 curl 返回 200，generate 含家具列表、dialog 后 quotation 变化；
- [ ] 无密钥硬编码（`grep -rn "sk-\|api_key" .` 应为空或仅读环境变量）。

---

## 第 2 周：数据流梳理 + 补全单测

**目标**：agent 摸清模块职责，补齐测试覆盖，为后续替换 Mock 打底。

**Agent 指令：**
```
1. 阅读 interior_design_agent/home_agent_mvp/ 下的代码：app.py、agents/*.py、engineering/bom.py、render/mock_render.py、data/*.json|yaml。
   画一张"请求从 /generate 到返回"的数据流图（文字版即可），标出每个模块职责与调用的函数。
   重点说明：scheme.json 如何被各模块读写？约束引擎在哪一步介入？对话修改如何反映到 quotation？
   交付：不超过 400 字的数据流说明 + 你发现的 3 个潜在改进点。

2. 在 tests/ 下新建 test_generator.py、test_bom.py，补齐用例：
   - generator.generate 对"多收纳"需求能追加 wardrobe；
   - generator.generate 对空需求至少追加 1 件家具；
   - bom.calc_bom 计算 total = 各家具 price 之和；
   - constraint.evaluate 对"衣柜深度 500"（越界）应产生 optimize 提示；
   - dialog.handle_command 对"换成暖色调"应把 style 改为 warm。
   运行 pytest 必须全绿。交付：新测试文件 + 运行结果。
```

**验收清单：**
- [ ] 数据流说明逻辑清晰，3 个改进点合理；
- [ ] 新增 5 个用例全绿；
- [ ] 未改动 `scheme.json` 数据骨架契约（若改，需同步 README 结构说明）。

---

## 第 3 周：真规划 Agent（接 LLM）+ 户型识别选型

**目标**：planner 接真实 LLM 推理；户型识别给出 MVP 方案与接入骨架。

**Agent 指令：**
```
任务 A（planner 接真 LLM）：
把 interior_design_agent/home_agent_mvp/agents/planner.py 占位实现替换为真实 LLM 调用（OpenAI 兼容接口，模型由环境变量 MODEL_NAME 指定；API Key 从 LLM_API_KEY 读取，不要硬编码）。
函数签名保持 plan(scheme, user_need) -> dict 不变。
功能：把 user_need（如"现代简约 两口之家 多收纳"）解析为结构化策略：
  {"rooms":[{"type":"bedroom","functions":[...]}], "furniture_draft":[{"cat":"wardrobe","qty":1}], "style":"modern_minimal"}
LLM 只做语义推理，不要让它编造具体毫米尺寸。
加 plan_with_mock() 作为无 Key 时的降级（返回占位逻辑）。
写 test_planner.py：无 Key 时走 mock 返回合理结构；有 Key 时（后续提供）走真实调用。
交付：修改后的 planner.py + 测试 + 运行结果。不要提交任何密钥。

任务 B（户型识别选型）：
调研并给出 interior_design_agent 项目"户型图识别"可行方案（不超过 300 字）：
- 对比：(a) 调用现成 API/SaaS (b) 用开源模型 FloorSG/类似 (c) 自研 CV；
- 给出 MVP 推荐与理由（考虑单人团队、成本、精度）。
保持 understand.recognize(image_path) -> house dict 接口不变，给出推荐方案的接入骨架代码（可先留 TODO）。
交付：方案对比（写入 docs/ 或直接回复）+ recognize 接入骨架（含清晰 TODO 注释）。不要实际训练模型。
```

**验收清单：**
- [ ] planner 无 Key 降级可用，有 Key 时调用真实接口；
- [ ] LLM 输出仅语义层，无硬编毫米数；
- [ ] 识别方案对比给出明确 MVP 推荐 + 接入骨架；
- [ ] `grep -rn "sk-\|api_key" .` 无泄露。

---

## 第 4 周：真户型识别接入（Mock 替换）

**目标**：清晰 CAD 图 → 结构化 house JSON，墙体≥85%、尺寸误差≤8%（MVP 放宽）。

**Agent 指令：**
```
基于第 3 周选型的推荐方案，实现 interior_design_agent/home_agent_mvp/agents/understand.py 的 recognize(image_path) -> house dict，替换现有 Mock。
要求：
1. 输入一张清晰户型图（CAD/照片），输出 house dict（walls / rooms / doors / windows / 标注尺寸→毫米）；
2. 承重墙判定沿用保守策略，不确定的标 wall_type="suspect_load_bearing"，不擅自判定为可拆；
3. 在 scheme.json 中落 original_walls 基线（从 recognize 结果写入，供约束引擎比对）；
4. 提供 tests/test_understand.py，用一张样例图（放 data/samples/）跑通，断言墙体数>0、含 rooms。
验收指标（MVP 放宽）：清晰 CAD 图墙体召回≥85%，尺寸误差≤8%。
交付：understand.py + 测试 + 一张样例图 + 运行结果。不要训练大模型，优先接现成方案/FloorSG。
```

**验收清单（你拍板安全口径）：**
- [ ] recognize 输出结构能被 generator 消费；
- [ ] original_walls 基线正确写入；
- [ ] 承重墙保守标记，未见"疑似"被当可拆；
- [ ] 测试通过，样例图可复现。

---

## 第 5 周：真对话 Agent（Function Calling 替换正则）

**目标**：口语指令 → 精准改 scheme JSON，覆盖尺寸/位置/风格/数量。

**Agent 指令：**
```
把 interior_design_agent/home_agent_mvp/agents/dialog.py 的正则解析替换为 LLM Function Calling。
要求：
1. 定义函数集：edit_furniture（改尺寸/位置/数量）、apply_style（改风格）、move_furniture、add_furniture、remove_furniture；
2. LLM 解析口语指令 → 调用对应 function → 改 scheme.design；
3. 所有修改必须经 constraint.evaluate 校验，冲突时返回替代方案（不静默失败）；
4. 函数签名保持 handle_command(text, scheme) -> dict 不变，返回含 updated scheme + quotation；
5. 加 dialog_with_mock() 降级（无 Key 时用原正则逻辑）；
6. 扩展 tests/test_dialog.py：覆盖"主卧衣柜加长30cm""换成暖色调""把沙发移到靠窗""加一个床头柜"。
交付：dialog.py + 测试 + 运行结果。API Key 仍走环境变量，不硬编码。
```

**验收清单：**
- [ ] 4 类指令均改对 scheme 并刷新 quotation；
- [ ] 冲突（如越界/拆承重）返回替代方案而非崩溃；
- [ ] 约束引擎在 dialog 必经路径上；
- [ ] mock 降级可用。

---

## 第 6 周：构件库扩充（3 → 30+ 件）

**目标**：床/柜/桌/沙发/厨卫全品类，每件绑定 BOM 模板 + 单价。

**Agent 指令：**
```
扩充 interior_design_agent/home_agent_mvp/data/components.json，从当前 3 件扩到 30+ 件，覆盖：床（1.5/1.8m）、衣柜（多种进深）、书桌、餐桌、沙发（单人/三人）、橱柜、卫浴柜、床头柜等。
要求：
1. 每件含：id、cat、name、default_dims（长/宽/高 mm）、style_tags、bom_template（材料+用量公式）、unit_price；
2. 在 generator.py 中支持按 style_tags + furniture_draft 拼装合理多件布局（避免重叠，简单网格/贴墙布局即可）；
3. 更新 bom.py 用 components 的 unit_price 算量（替换写死价格）；
4. 补 test_components.py：断言 30+ 件、每件有 unit_price、generator 能按需求拼出≥3 件且不重叠。
交付：components.json + generator.py + bom.py + 测试 + 运行结果。
```

**验收清单：**
- [ ] 30+ 件，品类齐全，字段完整；
- [ ] generate 能产出合理多件布局；
- [ ] 报价来自构件库单价，非写死。

---

## 第 7 周：全链路整合联调 + 修 bug

**目标**：识别→规划→生成→对话→算量 端到端跑通，收敛前 6 周问题。

**Agent 指令：**
```
在 interior_design_agent/home_agent_mvp/ 做全链路联调：
1. 走通：上传图(recognize) → plan(LLM) → generate → dialog(LLM) → bom 的完整链路（用一张样例图 + 一条口语指令）；
2. 写 tests/test_pipeline.py 串起上述步骤（mock LLM/识别时走降级）；
3. 修复前 6 周累计的 bug 与 lint 警告（运行 pytest 全绿、read_lints 无 error）；
4. 输出一份"已知限制清单"（哪些场景识别/生成仍不准，标注 P0/P1）。
交付：test_pipeline.py + 限制清单 + 全绿运行结果。
```

**验收清单（你判卷）：**
- [ ] 全链路 pytest 通过；
- [ ] 已知限制清单你过目，P0 项你定处理优先级；
- [ ] 无密钥泄露、未破坏 scheme 契约。

---

## 第 8 周：承重墙/安全红线强化（P0 收口）

**目标**：拆承重墙 100% 阻断或强制确认，审计可追溯。

**Agent 指令：**
```
在 interior_design_agent/home_agent_mvp/ 强化安全红线：
1. constraint.py 增加 A 类红线规则集（拆承重墙 / 开大洞 / 移管井），与 T2.3 一致；
2. dialog.py 中任何 remove_wall / 开洞类意图先过红线规则，命中则返回 blocked + 需人工确认标记；
3. app.py 增加 /confirm_demolition 接口（接收确认 token + 操作内容），记录审计日志到 data/audit.log（谁、何时、确认了什么拆改）；
4. 补 test_safety.py：断言拆承重墙被阻断、确认后可执行、审计有记录。
交付：constraint.py + dialog.py + app.py + test_safety.py + 运行结果。
```

**验收清单（你拍板规则口径）：**
- [ ] 拆承重墙 100% 阻断或强制确认；
- [ ] 审计日志可追溯；
- [ ] 测试覆盖红线场景。

---

## 第 9 周：真渲染接入（前端 3D Viewer）

**目标**：浏览器能看到 3D 户型 + 家具，可旋转。

**Agent 指令：**
```
在 interior_design_agent 项目接入 3D 渲染：
1. 把 design/scheme JSON 转换为 Three.js 场景（墙体 + 家具箱体占位即可，不要求精细模型）；
2. 前端（新建 frontend/ 或集成进 Flask 模板）用 Three.js 展示，支持旋转/缩放；
3. render/mock_render.py 保留为无前端的降级；
4. 提供启动说明（如何看 3D 页面），写进 README 或 frontend/README；
5. 补 pytest 或前端简单冒烟（确保转换函数对样例 scheme 不出错）。
交付：前端代码 + 转换逻辑 + 启动说明 + 冒烟结果。
```

**验收清单：**
- [ ] 浏览器能看 3D 户型 + 家具，可旋转；
- [ ] 转换逻辑对样例 scheme 稳定；
- [ ] 启动说明清晰可复现。

---

## 第 10 周：工程出图生产化（PDF 交付包）

**目标**：导出 PDF 含效果 + 尺寸 + 图纸 + 报价，工长能看懂。

**Agent 指令：**
```
把 interior_design_agent/home_agent_mvp/engineering/bom.py 生产化并补出图：
1. bom.py 用 components.json 的 bom_template 生成分项算量 + 报价（分房间/分项）；
2. 新增 engineering/export_pdf.py：导出 PDF 交付包，含：平面图（用 mock 或简单绘制）、尺寸标注、水电点位（规则生成）、报价单；
3. 水电点位用规则引擎生成（不靠 LLM），参考 T5.3；
4. app.py 增加 /export 接口返回 PDF；
5. 补 test_export.py：断言 PDF 生成成功且含报价总额。
交付：bom.py + export_pdf.py + app.py + 测试 + 一份样例 PDF。
```

**验收清单：**
- [ ] PDF 含效果/尺寸/图纸/报价；
- [ ] 水电点位为规则生成（非 LLM 编造）；
- [ ] 报价与构件库一致。

---

## 第 11 周：H5 / 小程序外壳 + 对话实时同步

**目标**：真实用户能上传户型图 → 说话 → 拿方案；对话改一处全视图同步。

**Agent 指令：**
```
在 interior_design_agent 前端接对话与同步：
1. 前端页面支持：上传户型图 → 调 /generate → 显示 3D + 报价 → 输入框发口语指令 → 调 /dialog → 3D 与报价实时刷新；
2. 对话页显示变更 diff（价格/尺寸变化），参考 T6.6；
3. 方案快照/撤销重做（后端 /snapshot、/undo，基于 scheme 版本），参考 T6.4；
4. 确保改一处 → 3D/尺寸/报价同步刷新（先满足功能，性能<3s 为加分）；
5. 补前端冒烟测试或 pytest 覆盖 /snapshot /undo。
交付：前端对话页 + 后端快照接口 + 同步逻辑 + 冒烟结果。
```

**验收清单（你判卷）：**
- [ ] 上传→生成→对话→刷新闭环可用；
- [ ] 撤销重做可用；
- [ ] 改动同步到各视图。

---

## 第 12 周：真实用户测试 + 上线合规 + 收尾

**目标**：找 5–10 个真实装修小白测，记录卡点；合规文案 + 隐私脱敏。

**你亲自做（不可外包）：**
- 找 5–10 个真实装修小白，观察他们如何用产品，记录卡点（哪一步放弃、哪句话 agent 听不懂）；
- 拍板合规文案、隐私脱敏策略。

**Agent 指令（收尾支持）：**
```
在 interior_design_agent 做上线前收尾：
1. 根据第 11 周用户反馈，修复 Top 3 卡点（agent 能改的：指令解析失败、生成布局不合理等）；
2. 补充合规文案与隐私脱敏（参考 T8.3）：户型图上传后本地处理、不留存敏感信息说明、免责声明；
3. 写一份 README 快速上手（安装/运行/上传/对话/导出全流程）；
4. 全量 pytest 绿、read_lints 无 error，输出最终验收清单（对照 MVP 出口标准）。
交付：修复补丁 + 合规文案 + README + 全绿结果 + 验收清单。
```

**验收清单（你最终判卷）：**
- [ ] 真实用户测试记录归档；
- [ ] 合规/脱敏到位；
- [ ] 对照 MVP 出口标准（识别/生成/安全/渲染/对话/交付/体验）逐项过；
- [ ] README 可让新人 10 分钟跑起来。

---

## 附：每周通用判卷清单（每次都查）

- [ ] `pytest` 全绿？
- [ ] `grep -rn "sk-\|api_key" .` 无硬编码密钥？
- [ ] 是否破坏 `scheme.json` 数据骨架契约（动了要同步 README）？
- [ ] LLM 是否只推理、没编造毫米尺寸？
- [ ] 约束引擎 `constraint.evaluate` 是否仍在 `generate`/`dialog` 必经路径？

> 判卷不过就打回 agent 重做，不要自己下手改——保持「你判卷、agent 干活」的分工。
