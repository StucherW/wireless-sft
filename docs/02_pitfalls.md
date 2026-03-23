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


