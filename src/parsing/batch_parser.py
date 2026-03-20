import os
import shutil
import json
import subprocess
from pathlib import Path
from loguru import logger

# =====================================================================
# 🚀 强制设置 HuggingFace 环境变量
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HOME"] = r"D:\Code_Place\Model\HuggingFace_Cache"

# 🚀 强制 Python 忽略系统代理（解决 127.0.0.1:7890 导致的 SSL 报错）
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
# =====================================================================

class BatchMinerUParser:
    def __init__(self, raw_dir: str, parsed_dir: str, temp_dir: str, cleanup_enabled: bool = True):
        """
        初始化批处理解析器
        :param raw_dir: 原始论文 PDF 存放目录
        :param parsed_dir: 解析结果输出目录
        :param temp_dir: 临时工作目录
        :cleanup_enabled: 调试开关
        """

        self.raw_dir = Path(raw_dir)
        self.parsed_dir = Path(parsed_dir)
        self.temp_dir = Path(temp_dir)
        self.cleanup_enabled = cleanup_enabled
        # python3 引入的pathlib，面向对象的路径，可以直接 / 拼接路径
        self.mapping_file = self.parsed_dir / "paper_mapping.json"

        self.parsed_dir.mkdir(parents=True, exist_ok = True)
        self.temp_dir.mkdir(parents=True, exist_ok = True)

    def is_already_parsed(self, paper_id: str) -> bool:
        """检查论文是否解析过"""
        output_folder = self.parsed_dir / paper_id
        if not output_folder.exists():
            return False
        
        md_files = list(output_folder.rglob(f"{paper_id}.md"))
        return len(md_files) > 0
    
    def load_mapping(self) -> dict:
        """读取论文映射关系"""
        if self.mapping_file.exists():
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_mapping(self, mapping: dict):
        """实时保存论文映射关系"""
        with open(self.mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=4, ensure_ascii=False)

    def cleanup_redundant_files(self, output_folder: Path, paper_id: str):
        """
        清理 MinerU 产生的中间文件，仅保留 Markdown 和图片
        """
        # 动态寻址: 递归搜出 MinerU 把文件输出在哪个子目录（hybrid/auto/ocr）
        md_files = list(output_folder.rglob(f"{paper_id}.md"))

        if not md_files:
            logger.error(f"{paper_id} 的 Markdown 文件没有生成，可能解析失败！")
            return 
        
        md_file = md_files[0]
        source_dir = md_file.parent  # MinerU 实际生成子目录（比如 hybrid_auto）
        
        if not self.cleanup_enabled:
            logger.info(f"💡 [调试模式] 已保留 {paper_id} 的原始输出目录结构 ({source_dir.name})。")
            return
        
        # 生产模式：提取核心内容
        target_md = output_folder / f"{paper_id}.md"
            
        if md_file != target_md:            
            shutil.move(str(md_file), str(target_md))
        
        source_images = source_dir / "images"       
        target_images = output_folder / "images"

        if source_images.exists() and source_images != target_images:
            if target_images.exists():
                shutil.rmtree(target_images)
            shutil.move(str(source_images), str(target_images))

        cleaned_count = 0
        for item in output_folder.iterdir():
            if item.name == f"{paper_id}.md" or item.name == "images":
                continue
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
            cleaned_count += 1
        
        logger.info(f"🧹 [生产模式] 已清理 {paper_id} 的 {cleaned_count} 个冗余文件。")

    def run_pipeline(self):
        """执行批处理解析流水线"""
        # 1. 获取所有的 pdf 文件
        pdf_files = list(self.raw_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"在 {self.raw_dir} 中没有找到 PDF 文件。")
            return 
        
        mapping = self.load_mapping()

        for idx, pdf_path in enumerate(pdf_files, start=1):
            original_name = pdf_path.stem

            # 2. 建立 paper id，格式样例 P00001
            if original_name in mapping:
                paper_id = mapping[original_name]
            else:
                existing_ids = [int(v.replace('P', '')) for v in mapping.values() if v.startswith('P')]
                next_id_num = max(existing_ids) + 1 if existing_ids else 1
                paper_id = f"P{next_id_num:05d}"

                mapping[original_name] = paper_id

            # 3. 检查是否已经解析
            if self.is_already_parsed(paper_id):
                logger.info(f"⏭️ 跳过已解析文件：{original_name} ({paper_id})")
                continue

            logger.info(f"🚀 正在处理 [{idx}/{len(pdf_files)}]: {original_name} -> {paper_id}")

            # 4. 拷贝到临时目录
            temp_pdf_path = self.temp_dir / f"{paper_id}.pdf"
            shutil.copy2(pdf_path, temp_pdf_path)

            # 5. 组装 MinerU 命令
            cmd = [
                "mineru",
                "-p", str(temp_pdf_path),
                "-o", str(self.parsed_dir),
                "-m", "auto"
            ]

            try:
                subprocess.run(cmd, check=True)
                # 保存输出，并根据 cleanup_enabled 开关清理 MinerU 中间文件
                output_folder = self.parsed_dir / paper_id
                self.cleanup_redundant_files(output_folder, paper_id)

            except subprocess.CalledProcessError as e:
                logger.error(f"❌ 解析失败: {paper_id}, 错误信息: {e}")
            
            finally:
                # 清理临时文件（重命名 PDF ）
                if temp_pdf_path.exists():
                    temp_pdf_path.unlink()
            
            self.save_mapping(mapping)

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    RAW_DIR = PROJECT_ROOT / "data" / "raw"
    PARSED_DIR = PROJECT_ROOT / "data" / "parsed"
    TEMP_DIR = PROJECT_ROOT / "data" / "temp"

    parser = BatchMinerUParser(
        raw_dir=RAW_DIR,
        parsed_dir=PARSED_DIR,
        temp_dir=TEMP_DIR,
        cleanup_enabled=False
    )

    parser.run_pipeline()