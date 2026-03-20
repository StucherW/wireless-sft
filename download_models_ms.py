import os
import sys
import json
import shutil
from pathlib import Path
from modelscope.hub.snapshot_download import snapshot_download

def get_user_dir():
    return str(Path.home())

def update_config(model_dir):
    user_dir = get_user_dir()
    config_path = os.path.join(user_dir, "magic-pdf.json")
    
    if not os.path.exists(config_path):
        print(f"Config file not found at {config_path}. Creating a default one.")
        default_config = {
            "models-dir": model_dir,
            "device-mode": "cuda",
            "table-config": {
                "model": "tablemaster",
                "enable": False,
                "max_time": 400
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        config["models-dir"] = model_dir
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            
    print(f"Successfully updated models-dir in {config_path} to {model_dir}")

def main():
    # ModelScope 上的新仓库地址
    repo_id = "opendatalab/PDF-Extract-Kit-1.0"
    
    # 你指定的本地保存目录
    local_dir = r"D:\Code_Place\Model\MinerU_Models"    
    os.makedirs(local_dir, exist_ok=True)
    
    print(f"Start downloading models from ModelScope repo: {repo_id}")
    try:
        # 【修正的地方】：用 model_dir 接收下载返回的实际路径
        model_dir = snapshot_download(repo_id, cache_dir=local_dir)
        
        print(f"Models downloaded successfully to: {model_dir}")
        update_config(model_dir)
    except Exception as e:
        print(f"Failed to download models: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
