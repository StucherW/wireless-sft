# 数据解析引擎：标准执行流程说明

## 1. 模块定位
本模块负责将非结构化的学术 PDF 论文，转换为包含高质量 LaTeX 公式与层级标题的 Markdown 文件，作为下游 SFT 数据合成的唯一输入。

## 2. 核心工具：MinerU (`-m auto` 模式)
在批处理脚本中，MinerU 被配置为 `auto` 混合路由模式，其单次解析的底层流水线如下：

1. **VLM 全页级版面理解**：调用 1.2B 视觉大模型扫描全页，输出结构化 Layout（标题、正文、公式、表格、图片）。
2. **阅读顺序重排**：基于 Layout 信息进行逻辑块（Block）级排序，恢复人类阅读顺序。
3. **公式检测与识别 (MFD & MFR)​**：裁剪公式区域，调用专有模型将其精确翻译为 LaTeX 代码（耗时最长环节）。
4. **OCR 兜底识别**：对扫描版文本或图片内文字调用 PaddleOCR 进行提取。
5. **结果组装与输出**：生成最终的 Markdown 文件及配图。

## 3. 批处理流水线 (Batch Pipeline) 工作流
为实现无人值守的自动化处理，`batch_parser.py` 执行以下标准工作流：

1. **扫描输入**：读取 `data/raw/` 下的所有 PDF 文件。
2. **ID 分配**：查询 `paper_mapping.json`，为新论文分配全局唯一短 ID（如 `P00001`）。
3. **状态检查**：通过递归搜索检查目标目录是否已存在 `.md` 文件，若存在则跳过（断点续传）。
4. **隔离执行**：将原始 PDF 复制到 `data/temp/` 并重命名为短 ID，调用 MinerU 核心引擎。
5. **资产提取与清理**：
   - **生产模式**：提取 `.md` 和 `images/`，拍平目录，删除其余数十 MB 的中间 JSON/PDF 垃圾。
   - **调试模式**：保留所有中间态文件供视觉检测框 Debug。
6. **状态持久化**：单次循环结束立即更新 mapping 文件。

## 4. 语义分块引擎 (Semantic Chunking) 工作流
本模块承接解析后的 Markdown 文件，负责将其转换为粒度适中、上下文完整的结构化 JSONL 数据，供大模型合成 QA 使用。

1. **输入读取**：递归扫描 `data/parsed/` 目录，读取所有标准化的 `Pxxxxx.md` 文件。
2. **状态机扫描与初切分**：
   - 逐行扫描文本，维护 `in_math_block` 状态机。
   - 若进入公式区（`$$` 或 `\begin{...}`），则锁定切分边界，将内容无条件追加，实现**公式原子化保护**。
   - 若在普通文本区，调用正则引擎识别**显式标题**（`###`）和**隐式标题**（`**A. System Model**`），遇到新标题即生成一个 Chunk。
3. **黑名单与长度过滤**：
   - 丢弃低价值章节（如 References, Appendix）。
   - 过滤长度极短（<100字符）的无意义碎片。
4. **超长章节二级切分（滑动窗口）​**：
   - 若 Chunk 长度超过 10000 字符，触发二级切分。
   - 按自然段落（`\n\n`）进行组装，达到阈值后截断。
   - 截断时，从末尾回溯提取 15% 的段落作为下一个 Sub-chunk 的开头（重叠区），生成带有 `(Part X)` 后缀的连续切块。
5. **数据落盘与监控**：
   - 高质量数据写入 `data/chunks/chunks.jsonl`。
   - 被丢弃的碎片和无效章节写入 `dropped_chunks.jsonl`，并附带 `drop_reason` 供人工抽查。

## 5. 数据合成引擎 (QA Generation) 工作流
本模块承接 Phase 2 的 Chunk 数据，利用大模型（Teacher Model）自动合成高质量的 Document-Grounded 问答对。

1. **状态检查与断点续传**：
   - 读取 `chunks.jsonl` 获取全量任务。
   - 分别读取 `qa_pairs.jsonl`（成功队列）和 `error_chunks.jsonl`（死信队列），收集已处理的 `chunk_id`。
   - 过滤得出 `pending_chunks`，实现精准的断点续传。
2. **异步并发调度**：
   - 使用 `asyncio.Semaphore` 设定并发锁（如 `MAX_CONCURRENCY = 64`），在不触发 API 429 限制的前提下榨干网络 I/O 吞吐量。
   - 结合 `tqdm.asyncio` 实时监控并发进度。
3. **强约束生成 (Structured Output)​**：
   - LLM 扮演 MobiCom/SIGCOMM 顶级审稿人。
   - 强制采用 Pydantic 定义的 Schema（包含 `type`, `difficulty`, `chain_of_reasoning`, `question`, `answer`, `reference_quote`）。
   - 通过 LangChain 的 `with_structured_output` 强制模型输出合法的 JSON 格式，并自动处理 LaTeX 转义。
4. **实时落盘与容错隔离**：
   - 采用追加模式 (`'a'`) 和 `flush()` 实时写入硬盘。
   - 遇到毫无价值的 Chunk（返回空列表），依然记录其 ID 以防重复处理。
   - 遇到爆 Token 或死循环的“毒数据”，将其隔离至死信队列，保证主流水线 100% 跑通。
