# 工程踩坑与排错指南 (Troubleshooting)

本指南记录了在 Windows 环境下部署本地大模型与视觉解析引擎时遇到的系统级坑点及解决对策。

## 1. 路径超长导致 FileNotFoundError (Windows 260 字符限制)
* **现象**：MinerU 模型推理已达到 100%，但在最后写入 `*_content_list.json` 时抛出 `FileNotFoundError`。
* **根因**：Windows 系统底层 API 默认限制绝对路径长度为 260 字符。学术论文原名极长，配合多级子目录，极易触发该限制导致写入崩溃。
* **对策**：废弃原文件名直接解析。引入 ID 映射机制，在临时目录使用 `P00001.pdf` 这种极短命名进行解析。

## 2. 网络代理冲突引发 SSLError
* **现象**：运行时抛出 `Max retries exceeded with url... (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]...`
* **根因**：系统开启了本地代理（如 `127.0.0.1:7890`），HuggingFace 国内镜像站（hf-mirror）拒绝了被代理软件修改过 SSL 证书的请求，导致连接被强行切断。
* **对策**：在 Python 脚本顶部强制注入环境变量，清空代理并锁定国内镜像源：
  ```python
  os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
  os.environ["HTTP_PROXY"] = ""
  os.environ["HTTPS_PROXY"] = ""

## 3. 正则表达式转义导致的边界失效
* **现象**：切分脚本无法识别任何标准的 Markdown 标题，整篇论文被当成一个巨大的 Chunk。
* **根因**：在编写正则时，误将捕获组的括号进行了转义（如写成 `^\(#{1,6})`），导致正则引擎去寻找真实的左括号字符，而非将其作为逻辑分组。
* **对策**：严格校验正则表达式的语法，显式标题匹配必须使用 `^(#{1,6})\s+(.*)`。

## 4. 暴力切分导致 LaTeX 公式断裂
* **现象**：大模型在 Phase 3 生成 QA 时产生严重幻觉，发现输入文本中的公式变成了残缺的代码（如只有 `\begin{equation}` 没有 `\end{equation}`）。
* **根因**：传统的按固定字符数（如 2000 字符）切分，或者单纯按标题切分时遇到了公式内部的 `#` 注释，导致算法从公式中间“拦腰一刀”。
* **对策**：引入轻量级状态机（State Machine）。通过 `in_math_block` 变量跟踪公式边界，一旦进入公式块，关闭所有切分判定，强制将公式视为不可分割的“原子块”。

## 5. 隐式标题降级导致章节黏连
* **现象**：某些核心章节（如 Methodology）异常庞大，发现 MinerU 将其次级标题解析成了加粗文本（如 `**A. CSI Preprocessing**`），导致未能触发切分。
* **对策**：在 `extract_header` 函数中增加隐式学术标题的正则兜底匹配（`PATTERN_IMPLICIT_HEADER`），专门抢救带有序号前缀的加粗文本，将其恢复为切分锚点。

## 6. 结构化输出导致 Token 爆炸 (Max Tokens Limit Reached)
* **现象**：极个别 Chunk 在处理时报错 `Could not parse response content as the length limit was reached`，消耗了高达 8192 个 Token。
* **根因**：大模型在处理结构化输出（JSON）时，遇到包含极其复杂的 LaTeX 矩阵或破损伪代码的文本，其底层注意力机制崩溃，陷入了无限重复生成推导步骤的死循环，直到撞穿 Token 上限。
* **对策**：
  1. 在 Prompt 中增加硬性约束：`Generate a MAXIMUM of 3 to 5 QA pairs` 和 `Keep chain_of_reasoning strictly under 150 words`。
  2. 在工程上建立“死信队列（Dead Letter Queue）”，将彻底失败的 Chunk 写入 `error_chunks.jsonl`，防止程序卡死在毒数据上。

## 7. 漏记空数据导致无限重试 (Infinite Retries on Empty Results)
* **现象**：重启脚本时，发现有几十个 Chunk 一直处于“待处理”状态，每次都被重新跑一遍。
* **根因**：Prompt 规定遇到无价值内容返回空列表 `[]`。原代码逻辑为 `if len(qa_pairs) > 0` 才写入日志。这导致大模型正确识别出的“废话 Chunk”没有被记录在 `processed_ids` 中，下次启动时被误认为未处理。
* **对策**：状态追踪必须基于“请求是否成功”，而不是“数据是否大于零”。修改逻辑为：只要没有抛出 Exception，即使生成的 QA 列表为空，也要写入成功日志，证明该 Chunk 已被成功“超度”。

