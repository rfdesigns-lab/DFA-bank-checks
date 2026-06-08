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
            system_uid TEXT,
            principal_fas TEXT,
            individual_fas TEXT,
            client_name TEXT,
            all_names TEXT,
            dob TEXT,
            physical_address TEXT,
            mailing_address TEXT,
            disability_flag INTEGER DEFAULT 0,
            assigned_officer TEXT,
            assigned_manager TEXT,
            hh_category TEXT,
            threshold_limit REAL,
            roi_status TEXT DEFAULT 'Not Uploaded',
            roi_link TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT,
            sent_at TEXT,
            bank TEXT,
            household_total REAL
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_system_uid ON cases(system_uid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_principal_fas ON cases(principal_fas)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_individual_fas ON cases(individual_fas)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_uid TEXT,
            principal_fas TEXT,
            individual_fas TEXT,
            client_name TEXT,
            assigned_officer TEXT,
            assigned_manager TEXT,
            bank TEXT,
            return_source TEXT,
            account_type TEXT,
            avg_balance REAL,
            current_balance REAL,
            status TEXT DEFAULT 'Returned',
            created_at TEXT
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_returns_system_uid ON returns(system_uid)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            email TEXT,
            role TEXT
        )
    """)

    # Seed staff if empty
    existing = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    if existing == 0:
        staff_seed = [
            ("Alice Thompson", "officer1@dfa.gov", "Officer"),
            ("Brian Clarke", "officer2@dfa.gov", "Officer"),
            ("Carmen Diaz", "officer3@dfa.gov", "Officer"),
            ("David Reynolds", "manager1@dfa.gov", "Manager"),
            ("Eva Martinez", "manager2@dfa.gov", "Manager"),
        ]
        conn.executemany(
            "INSERT INTO staff (full_name, email, role) VALUES (?,?,?)",
            staff_seed
        )

    conn.commit()
    conn.close()
    print("DB initialized successfully.")
