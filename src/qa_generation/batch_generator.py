import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from tqdm.asyncio import tqdm

from langchain_openai import ChatOpenAI
from src.qa_generation.schemas import QACollection
from src.qa_generation.prompts import qa_prompt_template

# ================================
# 1. 环境变量加载
# ================================
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE = os.getenv("OPENAI_API_BASE")

assert API_KEY is not None, "OPENAI_API_KEY is not set"
assert API_BASE is not None, "OPENAI_API_BASE is not set"

MAX_CONCURRENCY = 64

# ================================
# 2. 模型与 Chain 初始化
# ================================
MODEL_NAME = "gpt-4o-2024-08-06"  # 或 deepseek-chat

llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=API_KEY,
    base_url=API_BASE,
    temperature=0.1,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
)

# 强制 Structured Output
structured_llm = llm.with_structured_output(QACollection)
qa_chain = qa_prompt_template | structured_llm

# ================================
# 3. 异步处理核心逻辑
# ================================
async def process_chunk(chunk: dict, semaphore: asyncio.Semaphore) -> dict:
    """处理单个 Chunk ，受并发锁控制"""
    async with semaphore:
        chunk_id = f"{chunk.get('paper_id')}_{chunk.get('chunk_index')}"
        try:
            result:QACollection = await qa_chain.ainvoke({
                "paper_id": chunk.get("paper_id", "Unknown"),
                "section_title": chunk.get("section_title", "Unknown"),
                "content": chunk.get("content", "")
            })

            return {
                "chunk_id": chunk_id,
                "paper_id": chunk.get("paper_id"),
                "section_title": chunk.get("section_title"),
                "chunk_index": chunk.get("chunk_index"),
                "qa_pairs": [qa.model_dump() for qa in result.qa_list]
            }
        except Exception as e:
            print(f"\n[Error] Chunk {chunk_id} 处理失败：{str(e)}")
            return {
                "chunk_id": chunk_id,
                "error": str(e)
            }
        
# ================================
# 4. 主调度引擎
# ================================
async def main():
    input_file = Path("data/chunks/chunks.jsonl")
    output_dir = Path("data/qa_dataset")
    output_file = output_dir / "qa_pairs.jsonl"
    error_file = output_dir / "error_chunks.jsonl" # 死信队列，存放毒数据

    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = []
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            chunks.append(json.loads(line.strip()))

    print(f"📦 共加载 {len(chunks)} 个 Chunks。")

    processed_ids = set()

    # 1. 加载所有成功的 ID（包括生成了空列表的 Chunk）
    if output_file.exists():
        with output_file.open('r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line.strip())
                if "chunk_id" in data and "error" not in data:
                    processed_ids.add(data["chunk_id"])

    # 2. 加载所有彻底失败的 ID（毒数据，不再重试）
    if error_file.exists():
        with error_file.open('r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line.strip())
                processed_ids.add(data["chunk_id"])

    pending_chunks = [
        c for c in chunks 
        if f"{c.get('paper_id')}_{c.get('chunk_index')}" not in processed_ids
    ]

    print(f"🚀 已处理 {len(processed_ids)} 个，剩余 {len(pending_chunks)} 个待处理。")

    if not pending_chunks:
        print("✅ 所有 Chunk 已处理完毕！")
        return
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = [process_chunk(chunk, semaphore) for chunk in pending_chunks]

    # 🔧 同时打开成功日志和错误日志
    with output_file.open('a', encoding='utf-8') as out_f, \
        error_file.open('a', encoding='utf-8') as err_f:
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="合成 QA 中"):
            result = await future

            if "error" not in result:
                # 🔧 修复：只要没报错，哪怕 qa_pairs 是空的，也要写入记录，证明它被处理过了！
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                out_f.flush()
            else:
                # 🔧 修复：把爆 Token 的毒数据写入 error_file，下次启动就会自动跳过它
                err_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                err_f.flush()

# # ================================
# # 加载一个 Chunk（用于调试）
# # ================================
# def load_one_chunk(path: str, index: int = 0) -> dict:
#     """从 chunks.jsonl 中加载第 index 个 chunk"""
#     with open(path, "r", encoding="utf-8") as f:
#         for i, line in enumerate(f):
#             if i == index:
#                 return json.loads(line)
#     raise IndexError("Chunk index out of range")


# # ================================
# # 主入口（单 Chunk 调试）
# # ================================
# def main():
#     chunk_path = "data/chunks/chunks.jsonl"

#     # ✅ 先只拿第 0 个 chunk
#     chunk = load_one_chunk(chunk_path, index=0)

#     print("=== Loaded Chunk ===")
#     print(f"Paper ID: {chunk['paper_id']}")
#     print(f"Section: {chunk['section_title']}")
#     print(f"Content length: {len(chunk['content'])} chars")
#     print("====================\n")

#     # 调用 LLM
#     result: QACollection = qa_chain.invoke({
#         "paper_id": chunk["paper_id"],
#         "section_title": chunk["section_title"],
#         "content": chunk["content"],
#     })

#     print("=== Generated QACollection ===")
#     print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # main()
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
