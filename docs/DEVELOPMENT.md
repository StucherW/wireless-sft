# 无线感知垂类大模型 SFT 数据引擎 —— 开发执行文档

> 本文档是本项目 **唯一的开发执行入口**，用于：
> - 明确每一阶段的开发目标
> - 拆解可执行的子任务
> - 标注每个子任务的工程注意事项与风险点
>
> 📌 项目背景、整体架构与最终目标请参见 `README.md`  
> 📌 工程原理、踩坑记录与设计思考请参见 `docs/` 目录

---

## 🎯 项目总目标（对齐 README）

构建一条 **​“学术 PDF → 高质量 SFT 数据 → 垂类大模型”​** 的全自动化流水线，用于解决通用大模型在无线感知（Wireless Sensing）领域的专业幻觉问题。

---

## 🛠️ 开发总原则（全阶段通用）

1. **工程优先于 Demo**：宁可慢一点，也要保证可复现、可调试、可扩展
2. **调试 / 生产严格区分**：任何脚本都必须支持 Debug Mode
3. **事实驱动**：所有状态判断必须基于真实文件系统，而非路径假设
4. **第三方工具黑盒化**：MinerU / LLM 行为必须被工程逻辑“抹平”
5. **阶段收敛**：每个 Phase 完成后必须能独立验收

---

## 📅 开发阶段与任务拆解（Checklist）

---

## ✅ Phase 0：工程基建（Infrastructure）

**目标**：搭建稳定、可维护的工程骨架

### Sub-task 0.1：初始化仓库结构
- [√] 初始化 Git 仓库
- [√] 配置 `.gitignore`（忽略模型缓存、数据目录）
- [√] 建立标准目录结构（`src/`, `data/`, `docs/`）

⚠️ 注意事项：
- 禁止提交任何模型权重、PDF 原文、生成数据

---

### Sub-task 0.2：建立开发执行文档
- [√] 创建 `DEVELOPMENT.md`
- [√] 后续所有进度仅在此文件中更新

---

## ✅ Phase 1：数据解析引擎（Data Parsing Engine）

**目标**：将学术 PDF 稳定、无损地解析为 Markdown  
**当前状态：✅ 已完成并验证**

---

### Sub-task 1.1：MinerU 本地部署与单文件验证
- [√] Windows + GPU 本地部署 MinerU
- [√] 跑通 `-m auto` 全流程
- [√] 理解多阶段推理（VLM / MFD / MFR / OCR）

⚠️ 注意事项：
- `-m auto` 是多模型流水线，不是一次推理
- 首次运行会有模型加载一次性成本

---

### Sub-task 1.2：批处理脚本 `batch_parser.py`
- [√] 实现 PDF 批量解析
- [√] 使用 **ID 映射法** 规避 Windows 260 字符限制
- [√] 支持断点续传（幂等执行）
- [√] 支持 Debug / Production 两种模式
- [√] 输出结构标准化（目录拍平）

⚠️ 关键工程注意点：
- **状态判断必须使用递归搜索（`rglob`）​**
- 不得假设 MinerU 的输出目录结构（如 `hybrid_auto`）
- HuggingFace 模型缓存路径与代理必须在代码中锁死

✅ 本阶段产出：
- `src/parsing/batch_parser.py`
- `data/parsed/Pxxxxx/Pxxxxx.md`
- `paper_mapping.json`

---

## Phase 2：上下文感知的学术语义分块（Context-Aware Chunking）

**目标**：将 Markdown 转换为结构化 Chunk，在过滤无效内容的同时，最大限度保护长文本中的数学推导逻辑和上下文完整性。
**当前状态：进行中**

### Sub-task 2.1：智能边界识别与过滤
- [√] 显式与隐式标题识别：支持 Markdown 标准标题（`##`）以及学术论文常见的加粗次级标题（如 `**A. System Model**`）。
- [√] 黑名单过滤：自动丢弃 References, Appendix, Acknowledgments 等低价值章节。
- [√] 阈值放宽：大幅提升 Chunk 长度上限（如 10000 字符），让大模型在后续阶段能一次性“消化”完整的章节逻辑。

### Sub-task 2.2：超长章节的安全二级切分（核心难点）
- [√] 公式与代码块保护：识别 `$$...$$`、`\begin{}...\end{}` 等 LaTeX 公式边界，将其视为不可分割的“原子块”，绝对禁止从内部截断。
- [√] 重叠滑动窗口（Overlapping）：当必须切分超长章节时，相邻 Sub-chunk 之间保留 10%~20% 的重叠文本，确保变量定义（Notation）和上下文不丢失。

### Sub-task 2.3：工程实现与 Debug 机制
- [√] 实现 `semantic_chunker.py`，输出标准化的 `chunks.jsonl`。
- [√] 完善 Debug Mode，将丢弃的极短文本或无效章节输出至 `dropped_chunks.jsonl` 供人工抽查调优。

---

## 🚧 Phase 3：数据合成引擎（QA Generation）

**目标**：从 Chunk 自动合成高质量问答对

### Sub-task 3.1：Prompt 设计
- [ ] 设计无线感知领域强约束 Prompt
- [ ] 强制基于原文公式与推理

### Sub-task 3.2：批量 QA 生成
- [ ] 异步并发调用 LLM API
- [ ] 初步生成 QA 数据集

---

## 🚧 Phase 4：质量控制（Quality Control）

**目标**：剔除幻觉与低质量数据

### Sub-task 4.1：规则过滤
- [ ] 长度 / 拒答 / 格式过滤

### Sub-task 4.2：LLM-as-a-Judge
- [ ] 事实溯源校验
- [ ] 专业深度打分

---

## 🚧 Phase 5：微调与评估（Fine-tuning & Evaluation）

**目标**：验证数据价值，完成闭环

### Sub-task 5.1：SFT 微调
- [ ] 数据混合（8:2）
- [ ] QLoRA 微调

### Sub-task 5.2：自动化评估
- [ ] 基线对比
- [ ] 胜率与硬核子集分析

---

## ✅ 当前里程碑状态

- Phase 0：✅ 完成
- Phase 1：✅ 完成（稳定）
- Phase 2：⬅️ 即将开始（下一阶段）
