# 无线感知垂类大模型 SFT 数据引擎开发进度跟踪

## 🎯 项目总目标
构建“学术 PDF → SFT 数据 → 垂类大模型”的全自动化流水线，解决通用大模型在无线感知领域的专业幻觉问题。

## 🛠️ 开发工作流规范
1. **任务驱动**：严格按照本 Checklist 推进，完成一项打勾 `[x]`。
2. **调试与生产隔离**：关键脚本需提供 `debug` 开关（如保留中间文件）。
3. **节点提交**：每个子任务完成后，执行 `git add .` -> `git commit -m "feat: xxx"` 形成标准版本快照。

---

## 📅 开发计划清单 (Checklist)

### Phase 0: 工程基建 (Infrastructure)
- [√] **Sub-task 0.1**: 初始化 Git 仓库并配置 `.gitignore`。
- [√] **Sub-task 0.2**: 建立 `DEVELOPMENT.md` 进度跟踪文档。

### Phase 1: 数据解析引擎 (Data Parsing Engine)
- [√] **Sub-task 1.1**: 编写 MinerU 批处理脚本 `batch_parser.py`。
  - *需求*：解决 260 字符路径限制（ID 映射法）。
  - *需求*：增加自动化清理开关（调试阶段保留 JSON/Layout，生产阶段清理）。
- [ ] **Sub-task 1.2**: 编写语义分块脚本 `semantic_chunker.py`。
  - *需求*：基于 Markdown Header 进行切分，输出标准 JSONL。

### Phase 2: 数据合成引擎 (Data Synthesis Engine)
- [ ] **Sub-task 2.1**: 设计无线感知专属强约束 Prompt。
- [ ] **Sub-task 2.2**: 编写异步并发大模型 API 调用脚本 `qa_generator.py`。
- [ ] **Sub-task 2.3**: 跑通第一个 Chunk 的 QA 生成并进行人工抽检。

### Phase 3: 质量控制引擎 (Quality Control Engine)
- [ ] **Sub-task 3.1**: 编写基于规则的过滤器（长度、拒答词等）。
- [ ] **Sub-task 3.2**: 引入 LLM-as-a-Judge 脚本，进行事实溯源反向校验。

### Phase 4: 微调与评估 (Fine-tuning & Evaluation)
- [ ] **Sub-task 4.1**: 格式化数据为 Alpaca 格式，并按 8:2 混入通用数据。
- [ ] **Sub-task 4.2**: 在云算力平台部署 LLaMA-Factory 启动 QLoRA 微调。
- [ ] **Sub-task 4.3**: 运行自动化盲测评估，统计胜率与硬核子集准确率。
