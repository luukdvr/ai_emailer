from __future__ import annotations

import argparse
import os
import sys

from src.reply_checker import check_for_new_replies, get_reply_summary
from src.database import EmailDatabase


def main():
    parser = argparse.ArgumentParser(description="Check for replies to cold emails")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--mark-processed", type=int, help="Mark reply ID as processed")
    parser.add_argument("--show-all", action="store_true", help="Show all replies (including processed)")
    args = parser.parse_args()

    db = EmailDatabase()

    if args.stats:
        stats = db.get_stats()
        print("\n📊 Email Campaign Statistics:")
        print(f"   Total sent emails: {stats['total_sent']}")
        print(f"   Total replies: {stats['total_replies']}")
        print(f"   New (unprocessed) replies: {stats['new_replies']}")
        print(f"   Response rate: {stats['response_rate']}%")
        return

    if args.mark_processed:
        db.mark_reply_processed(args.mark_processed)
        print(f"✅ Marked reply {args.mark_processed} as processed")
        return

    if args.show_all:
        # This would require a new database method - for now just show new
        print("📬 Showing new replies only (--show-all not implemented yet)")

    print("🔍 Checking for new replies to your cold emails...")
    
    try:
        new_replies = check_for_new_replies()
        
        if not new_replies:
            print("✅ No new replies found")
            return
        
        summary = get_reply_summary(new_replies)
        
        print(f"\n🎉 Found {summary['total']} new reply(s)!\n")
        
        for i, company_info in enumerate(summary['companies'], 1):
            print(f"{i}. 📧 {company_info['company']}")
            print(f"   From: {company_info['prospect_name']} ({company_info['prospect_email']})")
            print(f"   Subject: {company_info['subject']}")
            print(f"   Received: {company_info['received_at']}")
            print(f"   Reply: {company_info['reply_content']}")
            print(f"   Reply ID: {company_info['reply_id']}")
            print()
        
        print("💡 Tip: Use --mark-processed <reply_id> to mark replies as handled")
        print("💡 Tip: Use --stats to see campaign statistics")
        
    except Exception as e:
        print(f"❌ Error checking for replies: {e}")
        print("Make sure you've authorized Gmail with readonly permissions")
        print("Delete token.json and run the emailer once to re-authorize")
        return 1


if __name__ == "__main__":
    sys.exit(main())