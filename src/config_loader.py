from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os
import importlib

def _load_toml(path: str) -> dict:
    # Prefer stdlib tomllib if available, else fall back to tomli
    mod = None
    try:
        mod = importlib.import_module("tomllib")
    except Exception:
        try:
            mod = importlib.import_module("tomli")
        except Exception as e:
            raise RuntimeError("Neither tomllib (3.11+) nor tomli is available. Install tomli.") from e
    with open(path, "rb") as f:
        return mod.load(f)


@dataclass
class GmailCfg:
    from_name: str
    from_email: str
    label: str


@dataclass
class GeminiCfg:
    api_key: str
    model: str = "gemini-1.5-flash-8b"


@dataclass
class CampaignCfg:
    service_name: str
    value_prop: str
    cta: str


@dataclass
class AppCfg:
    gmail: GmailCfg
    gemini: GeminiCfg
    campaign: CampaignCfg


def load_config(path: str) -> AppCfg:
    data = _load_toml(path)

    gmail = GmailCfg(**data.get("gmail", {}))
    gemini = GeminiCfg(**data.get("gemini", {}))
    campaign = CampaignCfg(**data.get("campaign", {}))

    return AppCfg(gmail=gmail, gemini=gemini, campaign=campaign)
