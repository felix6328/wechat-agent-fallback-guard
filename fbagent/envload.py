"""只读取 SILICONFLOW_API_KEY 这一行。

密钥文件里可能还有数据库、JWT 等其它变量。本模块只解析指定的那一行，
不会把其它变量读进进程，也不打印、不记录、不返回它们。调用方不得打印返回的 key。
查找顺序：环境变量 FB_ENV_FILE 指定的文件 → 仓库根目录 .env.local → .env
"""
from __future__ import annotations

import os
from pathlib import Path

from .paths import ROOT

KEY_NAME = "SILICONFLOW_API_KEY"


def _candidates() -> list[Path]:
    out = []
    if os.environ.get("FB_ENV_FILE"):
        out.append(Path(os.environ["FB_ENV_FILE"]))
    out += [ROOT / ".env.local", ROOT / ".env"]
    return out


def load_siliconflow_api_key() -> str:
    for p in _candidates():
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k.startswith("export "):
                k = k[7:].strip()
            if k == KEY_NAME:
                return v.strip().strip("'").strip('"')
    return ""
