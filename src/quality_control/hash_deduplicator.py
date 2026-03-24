import json
import re
from pathlib import Path
from datasketch import MinHash, MinHashLSH
from tqdm import tqdm

def get_shingles(text: str, n: int = 3) -> set:
    """
    分词与 Shingling ( N-gram 提取)
    把一句话拆成连续的词组
    进而 MinHash 计算字面重合度( Jaccard 相似度)
    """
    # 简单的正则分词，转小写并提取字母数字
    words = re.findall(r'\w', text.lower())
    if len(words) < n:
        return set(words)
    # 提取 n-gram
    return set([' '.join(words[i:i+n]) for i in range(len(words)-n+1)])

def main():
    input_file = Path("data/qa_dataset/cleaned_qa_pairs.jsonl")
    output_file = Path("data/qa_dataset/hash_deduplicated_qa.jsonl")

    if not input_file.exists():
        print(f"❌ 找不到输入文件: {input_file}")
        return
    # 1. 加载并拍平数据
    all_qas = []
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            chunk_data = json.loads(line.strip())
            for qa in chunk_data.get("qa_pairs", []):
                qa_item = {
                    "chunk_id": chunk_data.get("chunk_id", ""),
                    "paper_id": chunk_data.get("paper_id", ""),
                    "section_title": chunk_data.get("section_title", ""),
                    **qa
                }
                all_qas.append(qa_item)

    print(f"📦 共加载 {len(all_qas)} 条 QA 数据准备哈希去重。")

    # 2. 核心策略：按难度降序排序
    # 确保最先进入哈希桶的，一定是质量最高、推导最复杂的 QA

    all_qas.sort(key=lambda x: x.get("difficulty", 0), reverse=True)

    # 3. 初始化 LSH (Locality-Sensitive Hashing)
    # threshold: Jaccard 相似度阈值。0.75 意味着字面上约有 75% 的 n-gram 重合就会发生碰撞
    # num_perm: 哈希排列的次数，通常设为 128 或 256。越大越精准，但计算越慢
    THRESHOLD = 0.75
    NUM_PERM = 128
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=NUM_PERM)

    keep_qas = []
    dropped_count = 0

    print(f"⚙️ 启动 LSH 引擎 (Threshold={THRESHOLD}, Permutations={NUM_PERM})...")

    # 4. 遍历数据，计算哈希并利用碰撞去重
    for i, qa in enumerate(tqdm(all_qas, desc="哈希碰撞去重中")):
        question_text = qa["question"]

        shingles = get_shingles(question_text, n=3)
        m = MinHash(num_perm=NUM_PERM)
        for shingle in shingles:
            m.update(shingle.encode('utf-8'))

        result = lsh.query(m)
        if len(result) > 0:
            dropped_count += 1
        else:
            keep_qas.append(qa)
            lsh.insert(str(i), m)

    with output_file.open('w', encoding='utf-8') as out_f:
        for qa in keep_qas:
            out_f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    # ================================    
    # 打印去重报告    
    # ================================    
    print("" + "="*40)    
    print("🎯 LSH 哈希碰撞去重报告 (MinHash)")    
    print("="*40)    
    print(f"📝 原始 QA 总数: {len(all_qas)}")    
    print(f"💥 因哈希碰撞被剔除: {dropped_count}")    
    print(f"💎 最终保留的 Unique QA: {len(keep_qas)}")    
    print(f"📉 冗余率: {(dropped_count / len(all_qas)) * 100:.1f}%")    
    print("="*40)    
    print(f"🎉 去重完成！数据已保存至: {output_file}")

if __name__ == "__main__":
    main()

