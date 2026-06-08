"""
DFA Bank Check Processing Pipeline — Flask Web App
Simulates the full end-to-end pipeline:
  1. Officer Creates Case
  2. SharePoint List (SQLite)
  3. Flow 1 Intake Engine
  4. Officer Uploads ROI
  5. Flow 2 Friday Batch
  6. Banks Process Request
  7. Flow 3 Return Processing
  8. Flow 4 Household Aggregator
  9. CLEARED or OVER LIMIT
  10. Process Complete
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, redirect, url_for

from db import init_db, get_db

app = Flask(__name__)

THRESHOLDS = {
    "Standard": 5000.0,
    "Priority": 10000.0,
    "High Risk": 2500.0,
}


def _category_from_fas(fas_number: str) -> str:
    """Derive household category from last digit of FAS number."""
    digits = [c for c in fas_number if c.isdigit()]
    if not digits:
        return "Standard"
    last = int(digits[-1])
    if last <= 3:
        return "Standard"
    elif last <= 6:
        return "Priority"
    else:
        return "High Risk"


def _next_system_uid(conn) -> str:
    year = datetime.now(timezone.utc).year
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM cases WHERE system_uid LIKE ?",
        (f"DFA-{year}-%",),
    ).fetchone()
    seq = (row["cnt"] or 0) + 1
    return f"DFA-{year}-{seq:04d}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cases = conn.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()
    total = len(cases)
    pending_roi = sum(1 for c in cases if c["roi_status"] == "Not Uploaded")
    sent = sum(1 for c in cases if c["status"] == "Sent")
    resolved = sum(1 for c in cases if c["status"] in ("Cleared", "Over Limit"))
    conn.close()
    return render_template(
        "dashboard.html",
        cases=cases,
        total=total,
        pending_roi=pending_roi,
        sent=sent,
        resolved=resolved,
    )


@app.route("/cases/new", methods=["GET", "POST"])
def new_case():
    if request.method == "GET":
        return render_template("case_form.html")

    # Flow 1: Intake Engine
    fas = request.form.get("fas_number", "").strip()
    principal_fas = request.form.get("principal_fas", "").strip()
    aliases = request.form.get("aliases", "").strip()
    dob = request.form.get("dob", "").strip()
    address = request.form.get("address", "").strip()
    officer = request.form.get("assigned_officer", "").strip()
    manager = request.form.get("assigned_manager", "").strip()
    bank_name = request.form.get("bank_name", "").strip()
    bank_email = request.form.get("bank_email", "").strip()

    category = _category_from_fas(fas)
    threshold = THRESHOLDS[category]
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    uid = _next_system_uid(conn)
    conn.execute(
        """INSERT INTO cases
           (system_uid, fas_number, principal_fas, aliases, dob, address,
            assigned_officer, assigned_manager, status, roi_status,
            household_category, threshold, created_at, bank_name, bank_email)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            uid, fas, principal_fas, aliases, dob, address,
            officer, manager, "Pending", "Not Uploaded",
            category, threshold, now, bank_name, bank_email,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/cases/<int:case_id>")
def case_detail(case_id):
    conn = get_db()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    conn.close()
    if case is None:
        return "Case not found", 404
    return render_template("case_detail.html", case=case)


@app.route("/cases/<int:case_id>/upload-roi", methods=["POST"])
def upload_roi(case_id):
    conn = get_db()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if case is None:
        conn.close()
        return "Case not found", 404
    conn.execute(
        "UPDATE cases SET roi_status='Uploaded', roi_link=? WHERE id=?",
        (f"ROI_{case['system_uid']}.pdf", case_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("case_detail", case_id=case_id))


@app.route("/batch/run", methods=["POST"])
def batch_run():
    """Flow 2: Friday Batch — send all cases with ROI uploaded and status Pending."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, system_uid FROM cases WHERE roi_status='Uploaded' AND status='Pending'"
    ).fetchall()
    ids = [r["id"] for r in rows]
    uids = [r["system_uid"] for r in rows]
    if ids:
        conn.execute(
            f"UPDATE cases SET status='Sent', sent_at=? WHERE id IN ({','.join('?'*len(ids))})",
            [now] + ids,
        )
        conn.commit()
    conn.close()
    return jsonify({"processed": len(ids), "cases": uids})


@app.route("/cases/<int:case_id>/bank-response", methods=["POST"])
def bank_response(case_id):
    """Flow 3: Bank returns data."""
    try:
        balance = float(request.form.get("current_balance", 0))
    except ValueError:
        balance = 0.0

    conn = get_db()
    conn.execute(
        "UPDATE cases SET status='Return Received', current_balance=? WHERE id=?",
        (balance, case_id),
    )
    conn.commit()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    principal_fas = case["principal_fas"]
    conn.close()

    # Trigger Flow 4 automatically
    return redirect(url_for("aggregate_household", principal_fas=principal_fas))


@app.route("/household/aggregate/<path:principal_fas>", methods=["GET", "POST"])
def aggregate_household(principal_fas):
    """Flow 4: Household Aggregator."""
    conn = get_db()
    cases = conn.execute(
        "SELECT * FROM cases WHERE principal_fas=?", (principal_fas,)
    ).fetchall()

    eligible = [
        c for c in cases if c["status"] in ("Return Received", "Cleared", "Over Limit")
    ]
    total_balance = sum((c["current_balance"] or 0.0) for c in eligible)
    threshold = cases[0]["threshold"] if cases else 5000.0

    new_status = "Over Limit" if total_balance > threshold else "Cleared"

    ids = [c["id"] for c in cases]
    if ids:
        conn.execute(
            f"UPDATE cases SET status=? WHERE id IN ({','.join('?'*len(ids))})",
            [new_status] + ids,
        )
        conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
