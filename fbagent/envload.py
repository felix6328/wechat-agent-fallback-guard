"""Load only explicitly supported credentials from local configuration."""
from __future__ import annotations

import os
from pathlib import Path

from .paths import ROOT

KEY_NAME = "SILICONFLOW_API_KEY"
ALLOWED_KEYS = frozenset({
    KEY_NAME, "AMAP_KEY", "ALIPAY_APP_ID", "ALIPAY_APP_PRIVATE_KEY",
    "ALIPAY_APP_PRIVATE_KEY_FILE", "ALIPAY_PUBLIC_KEY", "ALIPAY_GATEWAY",
})


def _candidates() -> list[Path]:
    out = []
    if os.environ.get("FB_ENV_FILE"):
        out.append(Path(os.environ["FB_ENV_FILE"]).expanduser())
    out += [ROOT / ".env.local", ROOT / ".env"]
    return out


def load_setting(name: str) -> str:
    if name not in ALLOWED_KEYS:
        raise ValueError("Unsupported configuration field")
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
            if k == name:
                return v.strip().strip("'").strip('"')
    return ""


def load_siliconflow_api_key() -> str:
    return load_setting(KEY_NAME)
