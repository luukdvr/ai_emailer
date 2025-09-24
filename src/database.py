from __future__ import annotations

import sqlite3
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class SentEmail:
    id: Optional[int]
    thread_id: str
    message_id: str
    prospect_email: str
    prospect_name: str
    company: str
    subject: str
    body: str
    sent_at: datetime
    label: str


@dataclass
class EmailReply:
    id: Optional[int]
    sent_email_id: int
    message_id: str
    from_email: str
    reply_content: str
    received_at: datetime
    processed: bool = False


class EmailDatabase:
    def __init__(self, db_path: str = "data/emails.db"):
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    message_id TEXT UNIQUE NOT NULL,
                    prospect_email TEXT NOT NULL,
                    prospect_name TEXT,
                    company TEXT,
                    subject TEXT NOT NULL,
                    body TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    label TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_email_id INTEGER NOT NULL,
                    message_id TEXT UNIQUE NOT NULL,
                    from_email TEXT NOT NULL,
                    reply_content TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (sent_email_id) REFERENCES sent_emails (id)
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON sent_emails(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prospect_email ON sent_emails(prospect_email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON sent_emails(message_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reply_message_id ON replies(message_id)")
            
    def save_sent_email(self, email: SentEmail) -> int:
        """Save sent email to database, return the inserted ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO sent_emails 
                (thread_id, message_id, prospect_email, prospect_name, company, subject, body, sent_at, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email.thread_id,
                email.message_id,
                email.prospect_email,
                email.prospect_name,
                email.company,
                email.subject,
                email.body,
                email.sent_at,
                email.label
            ))
            return cursor.lastrowid

    def get_sent_emails(self, limit: Optional[int] = None) -> List[SentEmail]:
        """Get all sent emails, optionally limited."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM sent_emails ORDER BY sent_at DESC"
            if limit:
                query += f" LIMIT {limit}"
                
            rows = conn.execute(query).fetchall()
            return [
                SentEmail(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    message_id=row["message_id"],
                    prospect_email=row["prospect_email"],
                    prospect_name=row["prospect_name"],
                    company=row["company"],
                    subject=row["subject"],
                    body=row["body"],
                    sent_at=datetime.fromisoformat(row["sent_at"]),
                    label=row["label"]
                ) for row in rows
            ]

    def get_sent_email_by_thread_id(self, thread_id: str) -> Optional[SentEmail]:
        """Get sent email by thread ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sent_emails WHERE thread_id = ? LIMIT 1",
                (thread_id,)
            ).fetchone()
            
            if row:
                return SentEmail(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    message_id=row["message_id"],
                    prospect_email=row["prospect_email"],
                    prospect_name=row["prospect_name"],
                    company=row["company"],
                    subject=row["subject"],
                    body=row["body"],
                    sent_at=datetime.fromisoformat(row["sent_at"]),
                    label=row["label"]
                )
            return None

    def save_reply(self, reply: EmailReply) -> int:
        """Save email reply to database, return the inserted ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO replies 
                (sent_email_id, message_id, from_email, reply_content, received_at, processed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                reply.sent_email_id,
                reply.message_id,
                reply.from_email,
                reply.reply_content,
                reply.received_at,
                reply.processed
            ))
            return cursor.lastrowid

    def get_new_replies(self) -> List[EmailReply]:
        """Get all unprocessed replies."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT r.*, se.company, se.prospect_name, se.subject 
                FROM replies r 
                JOIN sent_emails se ON r.sent_email_id = se.id 
                WHERE r.processed = FALSE 
                ORDER BY r.received_at DESC
            """).fetchall()
            
            return [
                EmailReply(
                    id=row["id"],
                    sent_email_id=row["sent_email_id"],
                    message_id=row["message_id"],
                    from_email=row["from_email"],
                    reply_content=row["reply_content"],
                    received_at=datetime.fromisoformat(row["received_at"]),
                    processed=bool(row["processed"])
                ) for row in rows
            ]

    def mark_reply_processed(self, reply_id: int):
        """Mark a reply as processed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE replies SET processed = TRUE WHERE id = ?", (reply_id,))

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            sent_count = conn.execute("SELECT COUNT(*) FROM sent_emails").fetchone()[0]
            reply_count = conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
            new_replies = conn.execute("SELECT COUNT(*) FROM replies WHERE processed = FALSE").fetchone()[0]
            
            return {
                "total_sent": sent_count,
                "total_replies": reply_count,
                "new_replies": new_replies,
                "response_rate": round((reply_count / sent_count * 100), 2) if sent_count > 0 else 0
            }

    def get_thread_ids_for_monitoring(self) -> List[str]:
        """Get all thread IDs that should be monitored for replies."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT DISTINCT thread_id FROM sent_emails").fetchall()
            return [row[0] for row in rows]