import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.qa_generation.prompts import qa_prompt_template

load_dotenv()

# 1. 找到那个“罪魁祸首” Chunk P00015_19 P00015_19
target_paper_id = "P00015"
target_chunk_index = 19
target_chunk = None

with open("data/chunks/chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line.strip())
        if str(chunk["paper_id"]) == str(target_paper_id) and str(chunk.get("chunk_index", "")) == str(target_chunk_index):
            target_chunk = chunk
            break

if not target_chunk:
    print("❌ 没找到对应的 Chunk！")
    exit()

# 2. 剥离 Structured Output，直接肉眼观察
print(f"🔍 正在裸测 {target_paper_id}_{target_chunk_index} ...")
llm = ChatOpenAI(
    model="gpt-4o-2024-08-06",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    temperature=0.1,
    max_tokens=8192
)

# 直接调用普通的 LLM（不带 JSON 约束）
chain = qa_prompt_template | llm
response = chain.invoke({
    "paper_id": target_chunk["paper_id"],
    "section_title": target_chunk["section_title"],
    "content": target_chunk["content"],
})

# 打印前 2000 个字符和最后 2000 个字符，看看是不是在死循环
content = response.content
print("=== 头部内容 ===")
print(content[:2000])
print("=== 尾部内容 ===")
print(content[-2000:])
print(f"📊 总长度: {len(content)} 字符")
