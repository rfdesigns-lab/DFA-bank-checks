"""
DFA Bank Check Processing Pipeline — Flask Web App
Simulates the full end-to-end pipeline:
  1. Officer Creates Case (Flow 1 Intake Engine)
  2. Officer Uploads ROI
  3. Flow 2 Friday Batch
  4. Banks Process Request
  5. Flow 3 Return Processing
  6. Flow 4 Household Aggregator
  7. CLEARED or OVER LIMIT
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Flask, render_template, request, jsonify, redirect, url_for

from db import init_db, get_db

app = Flask(__name__)

BANKS = [
    "RBC", "CNB", "Butterfield", "CIBC", "FirstCaribbean",
    "Cayman National", "Fidelity", "ScotiaBank"
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_age(dob_str: str) -> int:
    """Calculate age in years from YYYY-MM-DD string."""
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 0


def _calc_hh_category(members: list[dict]) -> tuple[str, float]:
    """
    Given list of dicts with keys 'dob' and 'disability_flag',
    return (category, threshold).
    """
    for m in members:
        age = _calc_age(m.get("dob") or "")
        if age >= 60 or int(m.get("disability_flag") or 0) == 1:
            return "Special", 15000.0
    count = len(members)
    if count >= 4:
        return "Standard 4-6", 3500.0
    return "Standard 1-3", 3000.0


def _next_system_uid(conn) -> str:
    year = datetime.now(timezone.utc).year
    row = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) AS cnt FROM cases WHERE system_uid LIKE ?",
        (f"DFA-{year}-%",),
    ).fetchone()
    seq = (row["cnt"] or 0) + 1
    return f"DFA-{year}-{seq:05d}"


def _flow4(conn, principal_fas: str):
    """
    Flow 4 Household Aggregator.
    Recalculate category/threshold, then determine status for all cases
    sharing this principal_fas.
    """
    # 1. Get all cases rows for this principal_fas
    all_cases = conn.execute(
        "SELECT * FROM cases WHERE principal_fas=?", (principal_fas,)
    ).fetchall()

    if not all_cases:
        return

    # 2. Recalculate category/threshold
    members = [{"dob": c["dob"], "disability_flag": c["disability_flag"]} for c in all_cases]
    category, threshold = _calc_hh_category(members)

    # Update category/threshold on all rows for this principal_fas
    conn.execute(
        "UPDATE cases SET hh_category=?, threshold_limit=? WHERE principal_fas=?",
        (category, threshold, principal_fas)
    )

    # 3. Get all distinct system_uids for this principal_fas
    uid_rows = conn.execute(
        "SELECT DISTINCT system_uid FROM cases WHERE principal_fas=?",
        (principal_fas,)
    ).fetchall()
    all_uids = [r["system_uid"] for r in uid_rows]

    # 4. Count uids that are still "Sent to Banks" (pending return)
    pending_return_uids = set()
    for uid in all_uids:
        row = conn.execute(
            "SELECT status FROM cases WHERE system_uid=? LIMIT 1", (uid,)
        ).fetchone()
        if row and row["status"] == "Sent to Banks":
            pending_return_uids.add(uid)

    if pending_return_uids:
        # Still waiting for some banks — Partial Return
        conn.execute(
            "UPDATE cases SET status='Partial Return' WHERE principal_fas=?",
            (principal_fas,)
        )
    else:
        # All returned — compute household total
        row = conn.execute(
            "SELECT SUM(current_balance) AS total FROM returns WHERE principal_fas=?",
            (principal_fas,)
        ).fetchone()
        household_total = row["total"] or 0.0

        # Write household_total to all cases rows
        conn.execute(
            "UPDATE cases SET household_total=? WHERE principal_fas=?",
            (household_total, principal_fas)
        )

        if household_total > threshold:
            conn.execute(
                "UPDATE cases SET status='OVER LIMIT' WHERE principal_fas=?",
                (principal_fas,)
            )
        else:
            conn.execute(
                "UPDATE cases SET status='Cleared' WHERE principal_fas=?",
                (principal_fas,)
            )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()

    # Stats — count distinct system_uids
    total = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases"
    ).fetchone()[0]

    pending_roi = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases WHERE roi_status='Not Uploaded' AND status='Pending'"
    ).fetchone()[0]

    sent = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases WHERE status='Sent to Banks'"
    ).fetchone()[0]

    partial = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases WHERE status='Partial Return'"
    ).fetchone()[0]

    cleared = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases WHERE status='Cleared'"
    ).fetchone()[0]

    over_limit = conn.execute(
        "SELECT COUNT(DISTINCT system_uid) FROM cases WHERE status='OVER LIMIT'"
    ).fetchone()[0]

    # Get one representative row per system_uid (first alias row) with all aliases listed
    uid_rows = conn.execute(
        """
        SELECT c.*, GROUP_CONCAT(c2.client_name, ', ') AS all_aliases
        FROM cases c
        JOIN cases c2 ON c2.system_uid = c.system_uid
        WHERE c.id = (SELECT MIN(id) FROM cases WHERE system_uid = c.system_uid)
        GROUP BY c.system_uid
        ORDER BY c.id DESC
        """
    ).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        uid_rows=uid_rows,
        total=total,
        pending_roi=pending_roi,
        sent=sent,
        partial=partial,
        cleared=cleared,
        over_limit=over_limit,
    )


@app.route("/cases/new", methods=["GET", "POST"])
def new_case():
    conn = get_db()
    if request.method == "GET":
        officers = conn.execute("SELECT * FROM staff WHERE role='Officer'").fetchall()
        managers = conn.execute("SELECT * FROM staff WHERE role='Manager'").fetchall()
        conn.close()
        return render_template("case_form.html", officers=officers, managers=managers)

    # Flow 1: Intake Engine
    principal_fas = request.form.get("principal_fas", "").strip()
    individual_fas = request.form.get("individual_fas", "").strip()
    all_names_raw = request.form.get("all_names", "").strip()
    dob = request.form.get("dob", "").strip()
    physical_address = request.form.get("physical_address", "").strip()
    mailing_address = request.form.get("mailing_address", "").strip()
    disability_flag = 1 if request.form.get("disability_flag") else 0
    assigned_officer = request.form.get("assigned_officer", "").strip()
    assigned_manager = request.form.get("assigned_manager", "").strip()

    now = datetime.now(timezone.utc).isoformat()

    # 1. Generate system_uid
    uid = _next_system_uid(conn)

    # 2. Split aliases
    aliases = [a.strip() for a in all_names_raw.split(",") if a.strip()]
    if not aliases:
        aliases = [all_names_raw or "Unknown"]

    # 3. Validate staff
    officer_exists = conn.execute(
        "SELECT id FROM staff WHERE email=? AND role='Officer'", (assigned_officer,)
    ).fetchone()
    manager_exists = conn.execute(
        "SELECT id FROM staff WHERE email=? AND role='Manager'", (assigned_manager,)
    ).fetchone()

    if not officer_exists or not manager_exists:
        initial_status = "Incomplete"
    else:
        initial_status = "Pending"

    # 4. Get existing members of this principal_fas household
    existing_members = conn.execute(
        "SELECT dob, disability_flag FROM cases WHERE principal_fas=?",
        (principal_fas,)
    ).fetchall()

    # 5. Build full member list for category calculation (existing + new)
    all_members = [{"dob": m["dob"], "disability_flag": m["disability_flag"]} for m in existing_members]
    # Add new member(s) — one entry per alias (same dob/disability)
    for _ in aliases:
        all_members.append({"dob": dob, "disability_flag": disability_flag})

    # 6. Calculate category/threshold
    category, threshold = _calc_hh_category(all_members)

    # 7. Insert one row per alias
    for i, alias in enumerate(aliases):
        conn.execute(
            """INSERT INTO cases
               (system_uid, principal_fas, individual_fas, client_name, all_names,
                dob, physical_address, mailing_address, disability_flag,
                assigned_officer, assigned_manager, hh_category, threshold_limit,
                roi_status, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                uid, principal_fas, individual_fas,
                alias,
                all_names_raw if i == 0 else None,
                dob, physical_address, mailing_address, disability_flag,
                assigned_officer, assigned_manager,
                category, threshold,
                "Not Uploaded", initial_status,
                now,
            ),
        )

    # 8. Update existing cases rows for this principal_fas with new category/threshold
    conn.execute(
        "UPDATE cases SET hh_category=?, threshold_limit=? WHERE principal_fas=? AND system_uid!=?",
        (category, threshold, principal_fas, uid)
    )

    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/cases/<system_uid>/upload-roi", methods=["POST"])
def upload_roi(system_uid):
    conn = get_db()
    conn.execute(
        "UPDATE cases SET roi_status='Uploaded', roi_link=? WHERE system_uid=?",
        (f"ROI_{system_uid}.pdf", system_uid),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("case_detail", system_uid=system_uid))


@app.route("/batch/run", methods=["POST"])
def batch_run():
    """Flow 2: Friday Batch — send all cases with ROI Uploaded and status Pending."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()

    # Get eligible: Pending + ROI Uploaded — distinct system_uids
    eligible_rows = conn.execute(
        """SELECT DISTINCT system_uid FROM cases
           WHERE status='Pending' AND roi_status='Uploaded'"""
    ).fetchall()
    sent_uids = [r["system_uid"] for r in eligible_rows]

    if sent_uids:
        placeholders = ",".join("?" * len(sent_uids))
        conn.execute(
            f"UPDATE cases SET status='Sent to Banks', sent_at=? WHERE system_uid IN ({placeholders})",
            [now] + sent_uids,
        )
        conn.commit()

    # Skipped: Pending + ROI Not Uploaded
    skipped_rows = conn.execute(
        """SELECT DISTINCT assigned_officer FROM cases
           WHERE status='Pending' AND roi_status='Not Uploaded'"""
    ).fetchall()
    skipped_officers = [r["assigned_officer"] for r in skipped_rows if r["assigned_officer"]]

    conn.close()
    return jsonify({
        "processed": len(sent_uids),
        "skipped": len(skipped_officers),
        "sent_uids": sent_uids,
        "skipped_officers": skipped_officers,
    })


@app.route("/cases/<system_uid>")
def case_detail(system_uid):
    conn = get_db()
    alias_rows = conn.execute(
        "SELECT * FROM cases WHERE system_uid=? ORDER BY id", (system_uid,)
    ).fetchall()
    if not alias_rows:
        conn.close()
        return "Case not found", 404

    first = alias_rows[0]
    principal_fas = first["principal_fas"]

    returns = conn.execute(
        "SELECT * FROM returns WHERE system_uid=? ORDER BY id", (system_uid,)
    ).fetchall()

    # Household: all distinct system_uids for this principal_fas with latest status
    hh_uids = conn.execute(
        """SELECT DISTINCT system_uid FROM cases WHERE principal_fas=?""",
        (principal_fas,)
    ).fetchall()

    household = []
    for row in hh_uids:
        uid = row["system_uid"]
        cr = conn.execute(
            "SELECT * FROM cases WHERE system_uid=? ORDER BY id LIMIT 1", (uid,)
        ).fetchone()
        ret_sum = conn.execute(
            "SELECT SUM(current_balance) AS total FROM returns WHERE system_uid=?", (uid,)
        ).fetchone()
        household.append({
            "system_uid": uid,
            "client_name": cr["client_name"] if cr else "",
            "status": cr["status"] if cr else "",
            "balance_total": ret_sum["total"] or 0.0,
        })

    conn.close()
    return render_template(
        "case_detail.html",
        case=first,
        alias_rows=alias_rows,
        returns=returns,
        household=household,
        banks=BANKS,
    )


@app.route("/cases/<system_uid>/bank-return", methods=["POST"])
def bank_return(system_uid):
    """Flow 3: Simulate bank response."""
    bank = request.form.get("bank", "").strip()
    account_type = request.form.get("account_type", "").strip()
    try:
        avg_balance = float(request.form.get("avg_balance", 0))
    except ValueError:
        avg_balance = 0.0
    try:
        current_balance = float(request.form.get("current_balance", 0))
    except ValueError:
        current_balance = 0.0

    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()

    alias_rows = conn.execute(
        "SELECT * FROM cases WHERE system_uid=? ORDER BY id", (system_uid,)
    ).fetchall()

    if not alias_rows:
        conn.close()
        return "Case not found", 404

    principal_fas = alias_rows[0]["principal_fas"]

    # Duplicate guard: check if returns row exists for this system_uid + bank
    existing = conn.execute(
        "SELECT id FROM returns WHERE system_uid=? AND bank=?",
        (system_uid, bank)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE returns SET account_type=?, avg_balance=?, current_balance=?,
               return_source=?, status='Returned', created_at=?
               WHERE system_uid=? AND bank=?""",
            (account_type, avg_balance, current_balance, bank, now, system_uid, bank)
        )
    else:
        first_row = alias_rows[0]
        conn.execute(
            """INSERT INTO returns
               (system_uid, principal_fas, individual_fas, client_name,
                assigned_officer, assigned_manager, bank, return_source,
                account_type, avg_balance, current_balance, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                system_uid, first_row["principal_fas"], first_row["individual_fas"],
                first_row["client_name"], first_row["assigned_officer"], first_row["assigned_manager"],
                bank, bank, account_type, avg_balance, current_balance,
                "Returned", now
            )
        )

    # Update the cases row for this system_uid to reflect bank info
    conn.execute(
        "UPDATE cases SET bank=? WHERE system_uid=?", (bank, system_uid)
    )

    conn.commit()

    # Trigger Flow 4
    _flow4(conn, principal_fas)
    conn.commit()
    conn.close()

    return redirect(url_for("case_detail", system_uid=system_uid))


@app.route("/staff")
def staff_list():
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff ORDER BY role, full_name").fetchall()
    conn.close()
    return render_template("staff.html", staff=staff)


@app.route("/staff/add", methods=["POST"])
def staff_add():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "Officer").strip()
    if full_name and email:
        conn = get_db()
        conn.execute(
            "INSERT INTO staff (full_name, email, role) VALUES (?,?,?)",
            (full_name, email, role)
        )
        conn.commit()
        conn.close()
    return redirect(url_for("staff_list"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
