import json
from pathlib import Path
from collections import Counter

def check_latex_integrity(text: str) -> bool:
    """
    检查 LaTeX 公式的完整性。
    在无线感知学术语境中，'$' 符号几乎只用于 LaTeX 公式。
    如果 '$' 的总数是奇数，说明公式被截断或存在语法错误。
    """
    return text.count('$') % 2 == 0

def main():
    input_file = Path("data/qa_dataset/qa_pairs.jsonl")
    output_file = Path("data/qa_dataset/cleaned_qa_pairs.jsonl")
    
    if not input_file.exists():
        print(f"❌ 找不到输入文件: {input_file}")
        return

    # 统计指标
    stats = {
        "total_chunks_read": 0,
        "empty_chunks_dropped": 0,
        "total_qa_initial": 0,
        "valid_qa_final": 0,
        "latex_errors_dropped": 0
    }
    
    type_counter = Counter()
    difficulty_counter = Counter()
    
    cleaned_chunks = []

    print("🧹 开始清洗与校验数据...")
    
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            data = json.loads(line.strip())
            stats["total_chunks_read"] += 1
            
            # 1. 过滤空 Chunk
            qa_list = data.get("qa_pairs", [])
            if not qa_list:
                stats["empty_chunks_dropped"] += 1
                continue
                
            valid_qa_list = []
            for qa in qa_list:
                stats["total_qa_initial"] += 1
                
                # 2. LaTeX 完整性校验 (检查 question 和 answer)
                q_text = qa.get("question", "")
                a_text = qa.get("answer", "")
                if not check_latex_integrity(q_text) or not check_latex_integrity(a_text):
                    stats["latex_errors_dropped"] += 1
                    continue
                
                # 3. 统计有效数据分布
                qa_type = qa.get("type", "unknown")
                difficulty = qa.get("difficulty", 0)
                
                type_counter[qa_type] += 1
                difficulty_counter[difficulty] += 1
                
                valid_qa_list.append(qa)
            
            # 如果清洗后该 Chunk 还有有效的 QA，则保留
            if valid_qa_list:
                data["qa_pairs"] = valid_qa_list
                cleaned_chunks.append(data)
                stats["valid_qa_final"] += len(valid_qa_list)

    # 将清洗后的高质量数据落盘
    with output_file.open('w', encoding='utf-8') as out_f:
        for chunk in cleaned_chunks:
            out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # ================================
    # 打印数据体检报告
    # ================================
    print("\n" + "="*40)
    print("📊 SFT 数据集体检报告 (Phase 4)")
    print("="*40)
    print(f"📦 读取的 Chunk 总数: {stats['total_chunks_read']}")
    print(f"🗑️ 被丢弃的空 Chunk 数: {stats['empty_chunks_dropped']}")
    print("-" * 40)
    print(f"📝 初始 QA 对总数: {stats['total_qa_initial']}")
    print(f"✂️ 因 LaTeX 破损丢弃的 QA 数: {stats['latex_errors_dropped']}")
    print(f"✅ 最终获得的高质量 QA 数: {stats['valid_qa_final']}")
    print("-" * 40)
    
    print("📌 题型分布 (Type):")
    for t, count in type_counter.most_common():
        percentage = (count / stats['valid_qa_final']) * 100
        print(f"   - {t}: {count} ({percentage:.1f}%)")
        
    print("\n🔥 难度分布 (Difficulty):")
    # 按难度级别 1-5 排序打印
    for d in sorted(difficulty_counter.keys()):
        count = difficulty_counter[d]
        percentage = (count / stats['valid_qa_final']) * 100
        print(f"   - Level {d}: {count} ({percentage:.1f}%)")
    print("="*40 + "\n")
    print(f"🎉 清洗完成！终极 SFT 数据已保存至: {output_file}")

if __name__ == "__main__":
    main()
