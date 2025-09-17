from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class CampaignConfig:
    service_name: str
    value_prop: str
    cta: str


@dataclass
class Prospect:
    company: str
    contact_name: str
    email: str
    notes: str = ""


def simple_template(cfg: CampaignConfig, p: Prospect) -> tuple[str, str]:
    subject = f"{p.company} x {cfg.service_name}?"
    greeting = f"Hoi {p.contact_name}," if p.contact_name and p.contact_name.lower() not in ['', 'nan'] else "Hoi,"
    notes_text = p.notes if p.notes and p.notes.lower() not in ['', 'nan'] else "mogelijkheden voor optimalisatie"
    body = (
        f"{greeting}\n\n"
        f"Ik ben bezig met {cfg.service_name.lower()} voor MKB's. {cfg.value_prop}\n\n"
        f"Voor {p.company} zag ik: {notes_text}. "
        f"Lijkt het interessant om hier kort over te sparren? {cfg.cta}\n\n"
        f"Groet,\n"
        f"{{FROM_NAME}}"
    )
    return subject, body


def openai_generate(api_key: str, model: str, cfg: CampaignConfig, p: Prospect) -> tuple[str, str]:
    if not OpenAI:
        raise RuntimeError("openai package not available")
    client = OpenAI(api_key=api_key)
    system = (
        "Je bent een NL sales copywriter. Schrijf korte, beleefde cold emails (<= 120 woorden),"
        " met duidelijke waardepropositie en 1 concrete vraag. Gebruik eenvoudige taal en geen buzzwords."
    )
    user = (
        f"Doel: cold email voor service '{cfg.service_name}'.\n"
        f"Waardepropositie: {cfg.value_prop}.\n"
        f"CTA: {cfg.cta}.\n"
        f"Prospect: company='{p.company}', contact='{p.contact_name}', notes='{p.notes}'.\n"
        f"Geef output als JSON met velden subject en body. Gebruik { '{FROM_NAME}' } als placeholder voor de afzendernaam."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    content = resp.choices[0].message.content or "{}"

    import json
    try:
        data = json.loads(content)
        subject = data.get("subject") or f"{p.company} x {cfg.service_name}?"
        body = data.get("body") or ""
        return subject, body
    except Exception:
        # Fallback to template if parsing failed
        return simple_template(cfg, p)
