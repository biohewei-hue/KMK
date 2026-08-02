import json
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
DATA_DIR = os.path.join(ROOT, "data")


def load_config():
    with open(os.path.join(CONFIG_DIR, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_credentials():
    path = os.path.join(CONFIG_DIR, "credentials.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def day_dir(date_str):
    """data/YYYY-MM-DD/ 目录，不存在则创建。"""
    d = os.path.join(DATA_DIR, date_str)
    os.makedirs(d, exist_ok=True)
    return d


def save_json(date_str, name, obj):
    path = os.path.join(day_dir(date_str), f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    return path


def load_json(date_str, name):
    path = os.path.join(DATA_DIR, date_str, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
