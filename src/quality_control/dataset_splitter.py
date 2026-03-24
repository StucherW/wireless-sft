# src/quality_control/dataset_splitter.py

import json
import random
import os
from pathlib import Path
from collections import defaultdict

def to_alpaca_format(qa_item):
    """
    将原始 QA 项转换为带 <think> 标签的 Alpaca 格式。
    """
    section = qa_item.get("section_title", "General Wireless Sensing")
    question = qa_item.get("question", "No Question")
    answer = qa_item.get("answer", "No Answer")
    cot = qa_item.get("chain_of_reasoning", "No reasoning provided.")

    # 构建指令：利用 section_title 提供背景提示
    instruction = (
        "You are an expert in Wireless Sensing and Signal Processing. "
        "Please answer the following question rigorously and step-by-step."
        f"Context Hint: Topic related to '{section}'."
        f"Question:{question}"
    )

    # 构建输出：注入 <think> 标签模拟推理过程
    output = f"<think>{cot}</think>{answer}"

    return {
        "instruction": instruction,
        "input": "",
        "output": output,
        "system": "You are a highly professional AI assistant specialized in Wireless Sensing.",
        "history": [],
        "metadata": {
            "type": qa_item.get("type", "unknown"),
            "difficulty": qa_item.get("difficulty", 0),
            "paper_id": qa_item.get("paper_id", "unknown"),
            "factual_score": qa_item.get("judge_result", {}).get("factual_score", 0)
        }
    }

def main():
    # 路径定义
    input_file = Path("data/qa_dataset/judged_qa_pairs.jsonl")
    output_dir = Path("data/qa_dataset")
    
    train_output = output_dir / "train_sft.json"
    test_output = output_dir / "test_eval.json"
    rejected_output = output_dir / "rejected_qas.jsonl" # 存放不合格数据供分析
    
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_file.exists():
        print(f"❌ 找不到裁判打分后的输入文件: {input_file}")
        return

    # 1. 初始分流：合格 vs 不合格
    passed_qas = []
    rejected_qas = []
    
    with input_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): 
                continue
            try:
                item = json.loads(line.strip())
                # 依据裁判的 is_pass 字段进行分流
                if item.get("judge_result", {}).get("is_pass", False):
                    passed_qas.append(item)
                else:
                    rejected_qas.append(item)
            except json.JSONDecodeError:
                continue

    print(f"📦 数据分流统计:")
    print(f"   - 合格 (Passed): {len(passed_qas)}")
    print(f"   - 拒绝 (Rejected): {len(rejected_qas)}")

    # 2. 保存拒绝的数据（保留原始 JSONL 格式，方便后续分析幻觉原因）
    with rejected_output.open('w', encoding='utf-8') as f:
        for item in rejected_qas:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"🗑️ 不合格数据已存入回收站: {rejected_output}")

    # 3. 对合格数据进行分层抽样 (Stratified Sampling)
    # 按照难度 (Difficulty) 分层，确保测试集覆盖所有难度级别
    layers = defaultdict(list)
    for qa in passed_qas:
        difficulty = qa.get("difficulty", 3)
        layers[difficulty].append(qa)

    train_raw = []
    test_raw = []
    
    # 固定随机种子保证实验可复现
    random.seed(42)
    TEST_RATIO = 0.08 # 抽取 8% 作为测试集

    print("🧪 正在执行分层抽样...")
    for level, data in layers.items():
        random.shuffle(data)
        # 每一层至少抽 1 条到测试集
        split_idx = max(1, int(len(data) * TEST_RATIO))
        
        test_raw.extend(data[:split_idx])
        train_raw.extend(data[split_idx:])
        print(f"   - Level {level}: 总计 {len(data)}, 抽取测试项 {split_idx}")

    # 4. 转换为 Alpaca 格式并打乱
    train_alpaca = [to_alpaca_format(qa) for qa in train_raw]
    test_alpaca = [to_alpaca_format(qa) for qa in test_raw]
    
    random.shuffle(train_alpaca)
    random.shuffle(test_alpaca)

    # 5. 落盘保存
    with train_output.open('w', encoding='utf-8') as f:
        json.dump(train_alpaca, f, ensure_ascii=False, indent=2)
        
    with test_output.open('w', encoding='utf-8') as f:
        json.dump(test_alpaca, f, ensure_ascii=False, indent=2)

    print("\n" + "="*40)
    print("🎯 数据集最终交付报告")
    print("="*40)
    print(f"🔥 训练集 (Train SFT): {len(train_alpaca)} 条 -> {train_output.name}")
    print(f"🧪 测试集 (Test Eval):  {len(test_alpaca)} 条 -> {test_output.name}")
    print(f"🗑️ 回收站 (Rejected):  {len(rejected_qas)} 条 -> {rejected_output.name}")
    print("="*40)
    print(f"🎉 准备就绪！Phase 4 任务圆满完成。")

if __name__ == "__main__":
    main()
