"""
Database module for DFA Bank Check processing pipeline.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dfa_cases.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_uid TEXT UNIQUE,
            fas_number TEXT,
            principal_fas TEXT,
            aliases TEXT,
            dob TEXT,
            address TEXT,
            assigned_officer TEXT,
            assigned_manager TEXT,
            status TEXT DEFAULT 'Pending',
            roi_status TEXT DEFAULT 'Not Uploaded',
            roi_link TEXT,
            household_category TEXT,
            threshold REAL,
            current_balance REAL,
            created_at TEXT,
            sent_at TEXT,
            bank_name TEXT,
            bank_email TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("DB initialized successfully.")
