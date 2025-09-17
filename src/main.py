from __future__ import annotations

import argparse
import os
from typing import List

from .config_loader import load_config
from .gmail_client import get_service, ensure_label, send_message
from .writer import CampaignConfig, Prospect, simple_template, openai_generate


def load_prospects(csv_path: str) -> List[Prospect]:
    try:
        import pandas as pd  # type: ignore
        df = pd.read_csv(csv_path)
        req_cols = {"company", "contact_name", "email"}
        missing = req_cols - set(df.columns)
        if missing:
            raise ValueError(f"CSV mist kolommen: {', '.join(sorted(missing))}")
        prospects: List[Prospect] = []
        for _, row in df.iterrows():
            prospects.append(
                Prospect(
                    company=str(row.get("company", "")).strip(),
                    contact_name=str(row.get("contact_name", "")).strip(),
                    email=str(row.get("email", "")).strip(),
                    notes=str(row.get("notes", "")).strip(),
                )
            )
        return prospects
    except Exception:
        # Fallback CSV loader without pandas
        import csv
        prospects: List[Prospect] = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            req_cols = {"company", "contact_name", "email"}
            missing = req_cols - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV mist kolommen: {', '.join(sorted(missing))}")
            for row in reader:
                prospects.append(
                    Prospect(
                        company=(row.get("company") or "").strip(),
                        contact_name=(row.get("contact_name") or "").strip(),
                        email=(row.get("email") or "").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                )
        return prospects


def main():
    parser = argparse.ArgumentParser(description="AI cold emailer (Gmail)")
    parser.add_argument("--csv", default=os.path.join("data", "prospects.csv"), help="Pad naar prospects CSV (default: data/prospects.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Genereer en toon emails maar verzend niet")
    parser.add_argument("--limit", type=int, default=None, help="Maximaal aantal prospects om te verwerken")
    parser.add_argument("--only-email", type=str, default=None, help="Alleen deze email verzenden (filter)")
    args = parser.parse_args()

    cfg = load_config(os.path.join(os.path.dirname(__file__), "..", "config.toml"))

    service = None
    label_id = None
    if not args.dry_run:
        try:
            service = get_service()
            label_id = ensure_label(service, cfg.gmail.label)
        except RuntimeError as e:
            print("Fout tijdens Gmail setup:")
            print(str(e))
            print("\nStappen:")
            print("1) Enable Gmail API in Google Cloud Console for your project")
            print("2) Verwijder token.json en voer opnieuw uit om scopes te accepteren")
            return

    prospects = load_prospects(args.csv)
    if args.only_email:
        prospects = [p for p in prospects if p.email.lower() == args.only_email.lower()]
    if args.limit:
        prospects = prospects[: args.limit]
    if not prospects:
        print("Geen prospects om te verwerken (controleer CSV of filters)")
        return

    camp_cfg = CampaignConfig(
        service_name=cfg.campaign.service_name,
        value_prop=cfg.campaign.value_prop,
        cta=cfg.campaign.cta,
    )

    use_openai = bool(cfg.openai.api_key)

    for p in prospects:
        if use_openai:
            subject, body = openai_generate(cfg.openai.api_key, cfg.openai.model, camp_cfg, p)
        else:
            subject, body = simple_template(camp_cfg, p)

        # personalize From header
        sender_header = f"{cfg.gmail.from_name} <{cfg.gmail.from_email}>" if cfg.gmail.from_name else cfg.gmail.from_email

        # Fill placeholder
        body = body.replace("{FROM_NAME}", cfg.gmail.from_name or cfg.gmail.from_email)

        if args.dry_run:
            print("--- DRY RUN ---")
            print("To:", p.email)
            print("Subject:", subject)
            print("Body:\n", body)
            print("Label:", cfg.gmail.label)
            print()
            continue

        try:
            sent = send_message(service, p.email, subject, body, label_id, sender_header=sender_header)
            print(f"Sent to {p.email}: https://mail.google.com/mail/u/0/#sent/{sent.get('id')}")
        except RuntimeError as e:
            print(str(e))
            return


if __name__ == "__main__":
    main()
