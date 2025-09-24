from __future__ import annotations

import base64
from typing import List, Optional
from datetime import datetime
import re

from .gmail_client import get_service, get_thread_messages, get_message_content
from .database import EmailDatabase, EmailReply


def extract_text_from_payload(payload: dict) -> str:
    """Extract plain text from Gmail message payload."""
    text = ""
    
    # Check if it's a simple text message
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            text = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    
    # Check if it's HTML (fallback)
    elif payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            # Simple HTML to text conversion (remove tags)
            text = re.sub(r'<[^>]+>', '', html)
    
    # Handle multipart messages
    elif payload.get("mimeType", "").startswith("multipart/"):
        parts = payload.get("parts", [])
        for part in parts:
            part_text = extract_text_from_payload(part)
            if part_text:
                text = part_text
                break  # Prefer first text part
    
    return text.strip()


def is_reply_from_prospect(message: dict, prospect_email: str) -> bool:
    """Check if a message is a reply from the prospect (not our sent message)."""
    headers = message.get("payload", {}).get("headers", [])
    
    # Get From header
    from_header = ""
    for header in headers:
        if header.get("name", "").lower() == "from":
            from_header = header.get("value", "").lower()
            break
    
    # Check if it's from the prospect (not us)
    return prospect_email.lower() in from_header


def parse_reply_content(message: dict) -> str:
    """Parse reply content, removing quoted original message."""
    payload = message.get("payload", {})
    full_text = extract_text_from_payload(payload)
    
    if not full_text:
        return ""
    
    # Common patterns to detect quoted content
    quote_patterns = [
        r'\n\s*On\s+.*wrote:.*',  # "On ... wrote:"
        r'\n\s*Op\s+.*schreef:.*',  # Dutch "Op ... schreef:"  
        r'\n\s*From:.*',  # Email headers
        r'\n\s*Van:.*',   # Dutch "Van:"
        r'\n\s*>.*',      # Lines starting with >
        r'\n\s*-----Original Message-----.*',
    ]
    
    # Find the earliest quote pattern
    reply_text = full_text
    for pattern in quote_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
        if match:
            reply_text = full_text[:match.start()].strip()
            break
    
    return reply_text


def check_for_new_replies() -> List[EmailReply]:
    """Check Gmail for new replies to tracked emails."""
    db = EmailDatabase()
    service = get_service()
    
    new_replies = []
    thread_ids = db.get_thread_ids_for_monitoring()
    
    print(f"Checking {len(thread_ids)} threads for replies...")
    
    for thread_id in thread_ids:
        try:
            # Get sent email info for this thread
            sent_email = db.get_sent_email_by_thread_id(thread_id)
            if not sent_email:
                continue
                
            # Get all messages in thread
            messages = get_thread_messages(service, thread_id)
            
            # Look for replies from prospect
            for message in messages:
                message_id = message.get("id", "")
                
                # Skip if we already have this reply
                existing_replies = db.get_new_replies()
                if any(r.message_id == message_id for r in existing_replies):
                    continue
                
                # Check if it's a reply from the prospect
                if is_reply_from_prospect(message, sent_email.prospect_email):
                    # Get full message content
                    full_message = get_message_content(service, message_id)
                    
                    # Parse reply content
                    reply_content = parse_reply_content(full_message)
                    
                    if reply_content:
                        # Get timestamp
                        internal_date = int(full_message.get("internalDate", "0"))
                        received_at = datetime.fromtimestamp(internal_date / 1000)
                        
                        # Create reply record
                        reply = EmailReply(
                            id=None,
                            sent_email_id=sent_email.id,
                            message_id=message_id,
                            from_email=sent_email.prospect_email,
                            reply_content=reply_content,
                            received_at=received_at,
                            processed=False
                        )
                        
                        # Save to database
                        reply_id = db.save_reply(reply)
                        reply.id = reply_id
                        
                        new_replies.append(reply)
                        print(f"New reply from {sent_email.company} ({sent_email.prospect_email})")
                        
        except Exception as e:
            print(f"Error checking thread {thread_id}: {e}")
            continue
    
    return new_replies


def get_reply_summary(replies: List[EmailReply]) -> dict:
    """Generate summary of replies for display."""
    if not replies:
        return {"total": 0, "companies": []}
    
    db = EmailDatabase()
    companies = []
    
    for reply in replies:
        sent_email = db.get_sent_emails()  # This could be optimized with a join
        sent_info = next((se for se in sent_email if se.id == reply.sent_email_id), None)
        
        if sent_info:
            companies.append({
                "company": sent_info.company,
                "prospect_name": sent_info.prospect_name,
                "prospect_email": sent_info.prospect_email,
                "subject": sent_info.subject,
                "reply_content": reply.reply_content[:200] + "..." if len(reply.reply_content) > 200 else reply.reply_content,
                "received_at": reply.received_at.strftime("%Y-%m-%d %H:%M"),
                "reply_id": reply.id
            })
    
    return {
        "total": len(replies),
        "companies": companies
    }