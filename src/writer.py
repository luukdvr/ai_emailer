from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


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


def gemini_generate(api_key: str, model: str, cfg: CampaignConfig, p: Prospect) -> tuple[str, str]:
    if not genai:
        raise RuntimeError("google-generativeai package not available")
    
    genai.configure(api_key=api_key)
    
    # Configure the model
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,  # Fixed: was 64, max is 40 for Flash-8B
        "max_output_tokens": 300,
    }
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    
    model_instance = genai.GenerativeModel(
        model_name=model,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    
    system_prompt = (
        "Je bent een NL sales copywriter. Schrijf 1 korte, beleefde cold email (<= 120 woorden), "
        "met duidelijke waardepropositie en 1 concrete vraag. Gebruik eenvoudige taal en geen buzzwords. "
        "Geef output als EXACT dit JSON formaat (geen extra tekst, geen markdown): "
        '{"subject": "...", "body": "..."}. '
        "Gebruik {FROM_NAME} als placeholder voor de afzendernaam."
    )
    
    user_prompt = (
        f"Doel: cold email voor service '{cfg.service_name}'.\n"
        f"Waardepropositie: {cfg.value_prop}.\n"
        f"CTA: {cfg.cta}.\n"
        f"Prospect: company='{p.company}', contact='{p.contact_name}', notes='{p.notes}'.\n"
    )
    
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    
    try:
        response = model_instance.generate_content(full_prompt)
        content = response.text or "{}"
        
        # Clean up markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]   # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove ```
        content = content.strip()
        
        # Remove any text before first { or after last }
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx >= 0 and end_idx >= 0:
            content = content[start_idx:end_idx+1]
        
        import json
        try:
            data = json.loads(content)
            # Handle if it's an array instead of object (take first)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            subject = data.get("subject") or f"{p.company} x {cfg.service_name}?"
            body = data.get("body") or ""
            
            print(f"DEBUG: Successfully parsed Gemini response")
            return subject, body
        except Exception as e:
            print(f"DEBUG: JSON parsing failed: {e}")
            print(f"DEBUG: Cleaned content: {content}")
            # Fallback to template if parsing failed
            return simple_template(cfg, p)
    except Exception as e:
        print(f"DEBUG: Gemini API call failed: {e}")
        # Fallback to template if API call failed
        return simple_template(cfg, p)
