import os
import requests
import json

# ======== 配置部分 ========
# 建议将 API Key 存放在环境变量中，避免硬编码泄露
# 在终端设置：export API_KEY="你的密钥"
API_KEY = "sk-VQ3IO9x1ZJNrh2PPUF0WCV1QdoSyyUEPUvhmoYmm9vPUG8Iz"
API_URL = "https://chatapi.zjt66.top/v1/chat/completions"  # 替换为你的大模型 API 地址

if not API_KEY:
    raise ValueError("未检测到 API_KEY，请先在环境变量中设置 API_KEY")

# ======== 请求函数 ========
def call_llm_api(prompt: str, model: str = "gpt-4o-2024-08-06"):
    """
    调用大模型 API 并返回结果
    :param prompt: 用户输入
    :param model: 模型名称
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个有帮助的AI助手"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()  # 检查 HTTP 状态码
        data = response.json()

        # 解析返回内容
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"API 返回格式异常: {json.dumps(data, ensure_ascii=False)}"

    except requests.exceptions.Timeout:
        return "请求超时，请检查网络或增加 timeout 时间"
    except requests.exceptions.RequestException as e:
        return f"请求失败: {e}"

# ======== 测试调用 ========
if __name__ == "__main__":
    test_prompt = "用一句话介绍 Python 的特点"
    result = call_llm_api(test_prompt)
    print("模型回复：", result)
