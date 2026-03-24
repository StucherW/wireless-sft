import os
from dotenv import load_dotenv
load_dotenv()

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

def main():
    input_file = Path("data/qa_dataset/cleaned_qa_pairs.jsonl")
    output_file = Path("data/qa_dataset/semantic_deduplicated_qa.jsonl")
    
    if not input_file.exists():
        print(f"❌ 找不到输入文件: {input_file}")
        return

    # 1. 把所有 QA 拍平（Flatten），方便进行全局对比
    all_qas = []
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            chunk_data = json.loads(line.strip())
            for qa in chunk_data.get("qa_pairs", []):
                # 把上下文信息也带上
                qa_item = {
                    "chunk_id": chunk_data.get("chunk_id", ""),
                    "paper_id": chunk_data.get("paper_id", ""),
                    "section_title": chunk_data.get("section_title", ""),
                    **qa
                }
                all_qas.append(qa_item)

    print(f"📦 共加载 {len(all_qas)} 条 QA 数据准备去重。")

    # 2. 按照难度 (Difficulty) 降序排序
    # 这样在去重时，如果遇到相似的问题，我们总是优先保留难度最高、最硬核的那一个
    all_qas.sort(key=lambda x: x.get("difficulty", 0), reverse=True)

    # 3. 加载轻量级向量模型 (约 80MB，自动下载，CPU 运行极快)
    print("🧠 正在加载 Embedding 模型 (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 4. 提取所有的问题文本并向量化
    print("⏳ 正在计算问题的语义向量...")
    questions = [qa["question"] for qa in all_qas]
    embeddings = model.encode(questions, show_progress_bar=True)

    # 5. 贪心聚类与去重 (Greedy Deduplication)
    SIMILARITY_THRESHOLD = 0.85  # 相似度阈值：>0.85 认为是同一个问题
    
    keep_indices = []
    dropped_count = 0
    
    print("🧹 正在进行高维语义去重...")
    # 计算所有问题之间的余弦相似度矩阵
    similarity_matrix = cosine_similarity(embeddings)

    # 记录某个 index 是否已经被判定为与前面的保留项重复
    is_dropped = np.zeros(len(all_qas), dtype=bool)

    for i in tqdm(range(len(all_qas)), desc="去重进度"):
        if is_dropped[i]:
            continue
            
        keep_indices.append(i)
        
        # 找到所有与当前问题 i 相似度大于阈值的后续问题，并将它们标记为丢弃
        # 因为数据已经按难度排序，所以保留的 i 绝对是这批相似问题中质量最高的
        similar_flags = similarity_matrix[i] > SIMILARITY_THRESHOLD
        
        # 自己不能干掉自己，且只干掉排在后面的（难度更低的）
        similar_flags[:i+1] = False 
        
        # 将这些相似项标记为 dropped
        new_drops = np.sum(similar_flags & ~is_dropped)
        dropped_count += new_drops
        is_dropped |= similar_flags

    # 6. 提取保留下来的高质量 QA
    deduplicated_qas = [all_qas[i] for i in keep_indices]

    # 7. 落盘保存
    with output_file.open('w', encoding='utf-8') as out_f:
        for qa in deduplicated_qas:
            out_f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    # ================================
    # 打印去重报告
    # ================================
    print("" + "="*40)
    print("🎯 语义去重报告 (Semantic Deduplication)")
    print("="*40)
    print(f"📝 原始 QA 总数: {len(all_qas)}")
    print(f"🗑️ 因语义重复被剔除: {dropped_count}")
    print(f"💎 最终保留的 Unique QA: {len(deduplicated_qas)}")
    print(f"📉 冗余率: {(dropped_count / len(all_qas)) * 100:.1f}%")
    print("="*40)
    print(f"🎉 去重完成！最高质量的数据已保存至: {output_file}")

if __name__ == "__main__":
    main()
