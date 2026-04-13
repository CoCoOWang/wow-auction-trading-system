import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# 示例访问：
# config["screen"]["width"]
# config["wow_window_titles"]
# config["vmx_paths"]
