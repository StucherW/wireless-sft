import json
from pathlib import Path

def main():
    input_file = Path("data/qa_dataset/judged_qa_pairs.jsonl")
    report_file = Path("data/qa_dataset/hallucination_report.md")
    
    if not input_file.exists():
        print(f"❌ 找不到裁判打分文件: {input_file}")
        return

    failed_qas = []
    
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            item = json.loads(line.strip())
            
            # 提取被裁判拒绝的数据
            judge = item.get("judge_result", {})
            if not judge.get("is_pass", False):
                failed_qas.append(item)

    print(f"🔍 正在生成幻觉报告，共发现 {len(failed_qas)} 条不合格数据...")

    with report_file.open('w', encoding='utf-8') as f:
        f.write("# ❌ Wireless Sensing SFT Data - Hallucination & Low Quality Report\n\n")
        f.write(f"This report contains {len(failed_qas)} QA pairs rejected by the LLM-as-a-Judge.\n\n")
        
        for i, item in enumerate(failed_qas):
            judge = item.get("judge_result", {})
            f.write(f"## Case {i+1}: Chunk {item.get('chunk_id')}\n")
            f.write(f"**​[Judge Verdict]​**\n")
            f.write(f"- Factual Score: {judge.get('factual_score')}/5\n")
            f.write(f"- Depth Score: {judge.get('depth_score')}/5\n")
            f.write(f"- **Reasoning:​** {judge.get('reasoning')}\n\n")
            
            f.write(f"**​[Question]​**\n{item.get('question')}\n\n")
            f.write(f"**​[Answer]​**\n{item.get('answer')}\n\n")
            f.write("-" * 50 + "\n\n")

    print(f"🎉 报告已生成: {report_file}")
    print(f"💡 建议：打开该 Markdown 文件，重点查看 Factual Score 低于 3 的案例。")

if __name__ == "__main__":
    main()
