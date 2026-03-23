import os
import json
import re
from pathlib import Path

# ==========================================
# 配置参数 (Configuration)
# ==========================================
INPUT_DIR = Path("data/parsed")
OUTPUT_DIR = Path("data/chunks")
OUTPUT_FILE = OUTPUT_DIR / "chunks.jsonl"
DEBUG_FILE = OUTPUT_DIR / "dropped_chunks.jsonl"  # 用于观察无效 Chunk 的日志文件

# 运行模式
DEBUG_MODE = True  # 开启后会输出 dropped_chunks.jsonl

# 过滤规则配置
IGNORE_SECTIONS = {"references", "appendix", "acknowledgments", "acknowledgment", "references & notes"}
MIN_CHUNK_LENGTH = 100    # 过滤极短 Chunk（字符数）
MAX_CHUNK_LENGTH = 10000  # 过滤极长 Chunk（字符数）
OVERLAP_RATIO = 0.15      # 超长截断重叠比例

# ==========================================
# 2. 正则表达式预编译 
# ==========================================
# 匹配 Markdown 标题
PATTERN_EXPLICIT_HEADER = re.compile(r'^(#{1,6})\s+(.*)')

# 匹配隐式标题
# 要求：以 **​ 开头，包含数字或单个字母加点，后跟文本，以 ​** 结尾
PATTERN_IMPLICIT_HEADER = re.compile(r'^\*\*(?:[A-Z0-9]{1,2}\.|[IVX]+\.)\s+(.*?)\*\*\s*$')

# 匹配 LaTeX 公式块开始与结束 (用于原子化保护)
# 注意：这里只是标记特征，实际保护逻辑会在遍历行时使用状态机实现
# PATTERN_MATH_BLOCK_START = re.compile(r'^\s*(\$\$|\\begin\{[a-zA-Z0-9*]+\})')
# PATTERN_MATH_BLOCK_END = re.compile(r'^\s*(\$\$|\\end\{[a-zA-Z0-9*]+\})')

# ==========================================
# 3. 辅助判断函数
# ==========================================
def extract_header(line: str) -> str:
    """
    判断一行文本是不是标题，如果是，返回干净的标题文本；否则返回 None 
    """
    line = line.strip()

    match_explicit = PATTERN_EXPLICIT_HEADER.match(line)
    if match_explicit:
        return match_explicit.group(2).strip()
    
    match_implicit = PATTERN_IMPLICIT_HEADER.match(line)
    if match_implicit:
        return match_implicit.group(1).strip()

    return None

# ==========================================
# 4. 核心切分逻辑：带公式保护状态机
# ==========================================
def parse_markdown_to_chunks(file_path: Path, paper_id: str) -> list:
    """
    按 Markdown 标题对单篇论文进行初步切分，确保多行公式块不被打断。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chunks = []
    current_title = "Abstract/Introduction" # 默认论文的第一章节
    current_content = []
    chunks_inx = 0

    in_math_block = False

    for line in lines:
        stripped_line = line.strip()
        # 状态机流转：检查是否进入公式快
        if stripped_line.startswith('$$'):
            if stripped_line == '$$':
                # 独立一行的 $$ ，反转状态
                in_math_block = not in_math_block
            elif stripped_line.endswith('$$') and len(stripped_line) > 2:
                # 单行公式不改变状态
                pass
            else:
                # 以 $$ 开头但是结尾不是 $$ ，说明进入了多行公式
                in_math_block = not in_math_block
        
        elif stripped_line.startswith('\\begin{'):
            in_math_block = True
        elif stripped_line.startswith('\\end{'):
            in_math_block = False

        ## 核心切分逻辑
        # 如果当前处于公式块内部，绝对不进行标题判断，直接将当前行追加到内容中
        if in_math_block:
            current_content.append(line)
            continue

        # 如果不在公式块内部，则安全地检查当前行是否为标题
        header_text = extract_header(line)

        if header_text:
            # 遇到新标题：1. 结算并保存旧的 Chunk
            text = "".join(current_content).strip()
            if text:
                chunks.append({
                    "paper_id": paper_id,
                    "section_title": current_title,
                    "content": text,
                    "chunk_index": str(chunks_inx)
                })
                chunks_inx += 1
            # 2. 初始化新的 Chunk
            current_title = header_text
            current_content = []
        else:
            # 普通正文行，直接追加
            current_content.append(line)
    
    # 循环结束后，结算文件末尾最后剩下的文本
    text = "".join(current_content).strip()
    if text:
        chunks.append({
            "paper_id": paper_id,
            "section_title": current_title,
            "content": text,
            "chunk_index": str(chunks_inx)
        })
    
    return chunks

# ==========================================
# 5. 超长 chunk 二级切分逻辑：带重叠滑动窗口
# ==========================================
def split_long_chunk_with_overlap(text: str, max_length: int, overlap_ratio: float) -> list:
    """
    将超长 Chunk 按段落拆分，并保持相邻子块之间有指定比例的文本重叠。
    """
    # 按 Markdown 的自然段落/公式块边界进行切分
    paragraphs = text.split('\n\n')
    sub_chunks = []

    current_paragraphs = []
    current_length = 0

    # 计算期望的重叠字符数
    overlap_size_target = int(max_length * overlap_ratio)

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        p_len = len(p)

        # 如果加入当前段落会超出最大长度，且当前池子里已经有内容了，则触发截断
        if current_length + p_len > max_length and current_length > 0:
            # 1. 结算当前 Chunk
            sub_chunks.append("\n\n".join(current_paragraphs))
            # 2. 构造滑动窗口（提取重叠部分）
            overlap_paragraphs = []
            overlap_length = 0
            # 从当前池子的末尾向前倒推，收集段落直到达到期望的重叠长度
            for op in reversed(current_paragraphs):
                # 至少保留一个段落作为重叠，或者直到凑够 overlap_size_target
                if overlap_length + len(op) <= overlap_size_target or not overlap_paragraphs:
                    overlap_paragraphs.insert(0, op) # 插入到头部，保持原有顺序
                    overlap_length += len(op) + 2   # 补偿 \n\n 的长度
                else:
                    break
                    
            # 3. 初始化下一个 Chunk（以重叠部分作为开头，并加上导致超载的新段落）
            current_paragraphs = overlap_paragraphs
            current_paragraphs.append(p)
            current_length = sum(len(x) for x in current_paragraphs) + (len(current_paragraphs) - 1) * 2
        else:
            # 安全长度内，继续向池子中追加段落
            current_paragraphs.append(p)
            current_length += p_len + (2 if current_length > 0 else 0)
    # 循环结束后，把最后剩下的部分加进去
    if current_paragraphs:
        sub_chunks.append("\n\n".join(current_paragraphs))

    return sub_chunks

# ==========================================
# 6. 主控函数：串联过滤与切分
# ==========================================
def process_and_filter_chunks():
    """
    遍历所有解析后的 MD 文件，执行过滤规则、状态机切分和二级切分，并写入 JSONL 。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_raw": 0,
        "valid_normal": 0,
        "salvaged_from_long": 0,
        "dropped_ignored_section": 0,
        "dropped_too_short": 0 
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out, \
        open(DEBUG_FILE, 'w', encoding='utf-8') as f_debug:

        for md_file in INPUT_DIR.rglob("*.md"):
            paper_id = md_file.stem

            # 调用带公式保护的初步切分
            raw_chunks = parse_markdown_to_chunks(md_file, paper_id)
            stats["total_raw"] += len(raw_chunks)

            for chunk in raw_chunks:
                title_lower = chunk["section_title"].lower()
                content_len = len(chunk["content"])

                # 规则 1：忽略低价值章节（黑名单过滤）
                if any(ignore_word in title_lower for ignore_word in IGNORE_SECTIONS):
                    stats["dropped_ignored_section"] += 1
                    if DEBUG_MODE:
                        chunk["drop_reason"] = "IGNORED_SECTION"
                        f_debug.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    continue
                
                # 规则 2：过滤极短 Chunk（剔除无用碎片）
                if content_len < MIN_CHUNK_LENGTH:
                    stats["dropped_too_short"] += 1
                    if DEBUG_MODE:
                        chunk["drop_reason"] = f"TOO_SHORT ({content_len} chars)"
                        f_debug.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    continue

                # 规则 3：处理超长 Chunk（调用滑动窗口二级切分）
                if content_len > MAX_CHUNK_LENGTH:
                    sub_texts = split_long_chunk_with_overlap(
                        chunk["content"],
                        MAX_CHUNK_LENGTH,
                        OVERLAP_RATIO
                    )

                    for sub_idx, sub_text in enumerate(sub_texts):
                        # 再次过滤切分后可能产生的极短碎片
                        if len(sub_text) < MIN_CHUNK_LENGTH:
                            continue
                        new_chunk = {
                            "paper_id": chunk["paper_id"],
                            # 标注 Part X，提示大模型这是连续的章节
                            "section_title": f"{chunk['section_title']} (Part {sub_idx + 1})",
                            "content": sub_text,
                            "chunk_index": f"{chunk['chunk_index']}-{sub_idx + 1}"
                        }
                        f_out.write(json.dumps(new_chunk, ensure_ascii=False) + "\n")
                        stats["salvaged_from_long"] += 1
                
                else:
                    # 正常长度的 Chunk 直接写入
                    f_out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    stats["valid_normal"] += 1
    total_valid = stats["valid_normal"] + stats["salvaged_from_long"]

    # 打印最终的执行报告    
    print("="*50)    
    print("🎯 Context-Aware Semantic Chunking 执行报告")    
    print("="*50)    
    print(f"📄 扫描论文数: {len(list(INPUT_DIR.rglob('*.md')))}")    
    print(f"✂️ 原始粗切 Chunk 总数: {stats['total_raw']}")    
    print("-" * 50)    
    print(f"❌ 丢弃 - 无效章节 (References等): {stats['dropped_ignored_section']}")    
    print(f"❌ 丢弃 - 长度过短 (<{MIN_CHUNK_LENGTH} chars): {stats['dropped_too_short']}")    
    print("-" * 50)    
    print(f"✅ 正常保留 Chunk 数: {stats['valid_normal']}")    
    print(f"♻️ 超长章节滑动切分产出 (带15%重叠): {stats['salvaged_from_long']}")    
    print(f"🌟 最终高质量 Chunk 数: {total_valid}")    
    print(f"💾 有效数据路径: {OUTPUT_FILE}")    
    print("="*50)

if __name__ == "__main__":
    process_and_filter_chunks()