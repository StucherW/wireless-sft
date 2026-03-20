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
