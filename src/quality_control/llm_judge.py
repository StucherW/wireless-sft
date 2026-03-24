import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from tqdm.asyncio import tqdm
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

class JudgeResult(BaseModel):
    factual_score: int = Field(description="事实溯源得分 (1-5)。5表示完全忠于原文，1表示严重幻觉或捏造。")
    depth_score: int = Field(description="专业深度得分 (1-5)。5表示极具学术深度，1表示表面问题。")
    reasoning: str = Field(description="打分理由（不超过30个词）。")
    is_pass: bool = Field(description="factual_score >= 4 且 depth_score >= 3 则为 True，否则 False。")

llm = ChatOpenAI(
    model="gpt-4o-2024-08-06",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    temperature=0.0, # 裁判必须绝对客观
    max_tokens=500,
    max_retries=3,
)
structured_judge = llm.with_structured_output(JudgeResult)

JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an impartial, strict meta-reviewer for Wireless Sensing academic datasets. Evaluate the QA pair against the original Content. If the Answer hallucinates formulas or concepts not in the Content, set is_pass to false."),
    ("user", "--- ORIGINAL CONTENT ---\n{content}\n\n--- GENERATED QA ---\nQuestion: {question}\nAnswer: {answer}\n\nEvaluate this QA pair.")
])
judge_chain = JUDGE_PROMPT | structured_judge

async def evaluate_qa(qa_item: dict, original_content: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        try:
            result: JudgeResult = await judge_chain.ainvoke({
                "content": original_content,
                "question": qa_item.get("question", ""),
                "answer": qa_item.get("answer", "")
            })
            qa_item["judge_result"] = result.model_dump()
        except Exception as e:
            qa_item["judge_result"] = {"is_pass": False, "error": str(e)}
        return qa_item

async def main():
    raw_chunks_file = Path("data/chunks/chunks.jsonl")
    input_file = Path("data/qa_dataset/semantic_deduplicated_qa.jsonl")
    output_file = Path("data/qa_dataset/judged_qa_pairs.jsonl")
    
    # 1. 加载原始 Content 字典
    content_map = {}
    with raw_chunks_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            c = json.loads(line.strip())
            chunk_id = f"{c.get('paper_id')}_{c.get('chunk_index')}"
            content_map[chunk_id] = c.get("content", "")
            
    # 2. 加载待评估的 QA
    all_qas = []
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            all_qas.append(json.loads(line.strip()))

    print(f"⚖️ 启动大模型裁判 (总数据: {len(all_qas)} 条)...")
    
    semaphore = asyncio.Semaphore(64) # 裁判并发可以高一点
    tasks = [evaluate_qa(qa, content_map.get(qa.get("chunk_id"), ""), semaphore) for qa in all_qas]
    
    passed_qas = []
    
    with output_file.open('w', encoding='utf-8') as out_f:
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="裁判评估中"):
            result = await future
            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
            if result.get("judge_result", {}).get("is_pass", False):
                passed_qas.append(result)

    print("\n" + "="*40)
    print("⚖️ LLM-as-a-Judge 评估报告")
    print("="*40)
    print(f"✅ 审核通过 (Pass): {len(passed_qas)}")
    print(f"❌ 审核拒绝 (Fail): {len(all_qas) - len(passed_qas)}")
    print(f"📉 淘汰率: {((len(all_qas) - len(passed_qas)) / len(all_qas)) * 100:.1f}%")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
