import json
from pathlib import Path

def main():
    # 🔧 读取通过了裁判审核的数据
    input_file = Path("data/qa_dataset/judged_qa_pairs.jsonl")
    output_file = Path("data/qa_dataset/sft_alpaca_dataset.json")
    
    if not input_file.exists():
        print(f"❌ 找不到输入文件: {input_file}")
        return

    alpaca_dataset = []
    
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            qa_item = json.loads(line.strip())
            
            # 🔧 严格过滤：只保留裁判判定为 Pass 的高质量数据
            judge_result = qa_item.get("judge_result", {})
            if not judge_result.get("is_pass", False):
                continue
            
            question = qa_item.get("question", "")
            answer = qa_item.get("answer", "")
            cot = qa_item.get("chain_of_reasoning", "")
            section = qa_item.get("section_title", "")
            
            # 🔧 Instruction 不再塞入长篇原文，而是利用 section_title 提供微小提示
            instruction = (
                "You are an expert in Wireless Sensing and Signal Processing. "
                "Please answer the following question rigorously and step-by-step.\n\n"
                f"Context Hint: This question is related to the topic of '{section}'.\n\n"
                f"Question:\n{question}"
            )
            
            # 🔧 引入类似 DeepSeek-R1 的 <think> 标签，极其适合当前大模型的 CoT 微调！
            output = (
                f"<think>\n{cot}\n</think>\n\n"
                f"{answer}"
            )
            
            alpaca_dataset.append({
                "instruction": instruction,
                "input": "",
                "output": output,
                "system": "You are a highly professional AI assistant specialized in Wireless Sensing.",
                "history": [],
                "metadata": {
                    "type": qa_item.get("type", ""),
                    "difficulty": qa_item.get("difficulty", 0),
                    "factual_score": judge_result.get("factual_score", 0),
                    "paper_id": qa_item.get("paper_id", "")
                }
            })

    with output_file.open('w', encoding='utf-8') as out_f:
        json.dump(alpaca_dataset, out_f, ensure_ascii=False, indent=2)

    print(f"🎉 成功转换 {len(alpaca_dataset)} 条黄金数据为 Alpaca 格式！")
    print(f"📁 文件保存在: {output_file}")

if __name__ == "__main__":
    main()
