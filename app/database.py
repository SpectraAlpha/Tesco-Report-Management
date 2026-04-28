"""SQLite database layer – schema creation, seeding and query helpers."""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lab_reports.db",
)


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Password hashing – PBKDF2-HMAC-SHA256 with a random salt
# Stored as "<hex_salt>:<hex_digest>" so the salt is always available.
# ---------------------------------------------------------------------------

_PBKDF2_ITERS = 600_000
_PBKDF2_HASH  = "sha256"


def _hash(password: str, salt_hex: str | None = None) -> str:
    """Return a salted PBKDF2 hash suitable for storage.

    Format: ``<16-byte hex salt>:<64-byte hex digest>``

    When *salt_hex* is provided (during verification) the same salt is reused;
    otherwise a fresh random salt is generated.
    """
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH, password.encode(), salt, _PBKDF2_ITERS
    )
    return f"{salt.hex()}:{digest.hex()}"


def _verify(password: str, stored: str) -> bool:
    """Return True when *password* matches the *stored* PBKDF2 hash."""
    try:
        salt_hex, _ = stored.split(":", 1)
        return secrets.compare_digest(stored, _hash(password, salt_hex))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    UNIQUE NOT NULL,
    password    TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    full_name   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS report_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    created_by  INTEGER REFERENCES users(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS template_variables (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id    INTEGER REFERENCES report_templates(id) ON DELETE CASCADE,
    name           TEXT    NOT NULL,
    unit           TEXT,
    normal_min     REAL,
    normal_max     REAL,
    has_status     INTEGER DEFAULT 1,
    display_order  INTEGER DEFAULT 0,
    color_pass     TEXT DEFAULT '#2ecc71',
    color_fail     TEXT DEFAULT '#e74c3c'
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    template_id  INTEGER REFERENCES report_templates(id),
    created_by   INTEGER REFERENCES users(id),
    audited_by   INTEGER REFERENCES users(id),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    audited_at   TIMESTAMP,
    status       TEXT DEFAULT 'draft',
    audit_notes  TEXT,
    sample_id    TEXT,
    patient_id   TEXT,
    patient_name TEXT
);

CREATE TABLE IF NOT EXISTS report_values (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id     INTEGER REFERENCES lab_reports(id) ON DELETE CASCADE,
    variable_name TEXT NOT NULL,
    value         TEXT,
    unit          TEXT,
    test_status   TEXT,
    has_status    INTEGER DEFAULT 1,
    display_order INTEGER DEFAULT 0,
    normal_range  TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER REFERENCES lab_reports(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    filepath    TEXT NOT NULL,
    file_type   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_DEFAULT_USERS = [
    ("technician1", "password", "technician",   "Alice Chen"),
    ("labmanager1", "password", "lab_manager",  "Dr. Sarah Johnson"),
    ("manager1",    "password", "manager",      "Michael Brown"),
]

_BLOOD_VARS = [
    # (name, unit, min, max, has_status, order)
    ("Glucose",        "mg/dL", 70.0,  100.0, 1, 1),
    ("Cholesterol",    "mg/dL",  0.0,  200.0, 1, 2),
    ("Triglycerides",  "mg/dL",  0.0,  150.0, 1, 3),
    ("HDL",            "mg/dL", 40.0, 9999.0, 1, 4),
    ("LDL",            "mg/dL",  0.0,  100.0, 1, 5),
    ("Creatinine",     "mg/dL",  0.7,    1.3, 1, 6),
    ("BUN",            "mg/dL",  7.0,   25.0, 1, 7),
    ("Sample Type",    None,    None,   None,  0, 8),
    ("Collection Date",None,    None,   None,  0, 9),
    ("Lab ID",         None,    None,   None,  0, 10),
]

_URINE_VARS = [
    ("pH",             None,     6.0,   7.5,  1, 1),
    ("Protein",        "mg/dL",  0.0,  14.0,  1, 2),
    ("Glucose",        "mg/dL",  0.0,   0.0,  1, 3),
    ("Ketones",        None,    None,  None,   1, 4),
    ("WBC",            "/hpf",   0.0,   5.0,  1, 5),
    ("RBC",            "/hpf",   0.0,   2.0,  1, 6),
    ("Sample Type",    None,    None,  None,   0, 7),
    ("Collection Time",None,    None,  None,   0, 8),
    ("Volume",         "mL",    None,  None,   0, 9),
]

_CBC_VARS = [
    ("WBC",            "10³/µL", 4.5,  11.0,  1, 1),
    ("RBC",            "10⁶/µL", 4.5,   5.9,  1, 2),
    ("Hemoglobin",     "g/dL",  13.5,  17.5,  1, 3),
    ("Hematocrit",     "%",     41.0,  53.0,  1, 4),
    ("MCV",            "fL",    80.0,  100.0, 1, 5),
    ("Platelets",      "10³/µL",150.0, 400.0, 1, 6),
    ("Neutrophils",    "%",     50.0,  70.0,  1, 7),
    ("Lymphocytes",    "%",     20.0,  40.0,  1, 8),
    ("Sample Type",    None,    None,  None,   0, 9),
    ("Draw Time",      None,    None,  None,   0, 10),
    ("Requisition ID", None,    None,  None,   0, 11),
]


def init_db() -> None:
    """Create tables and seed default data if the database is new."""
    conn = _connect()
    cur = conn.cursor()
    cur.executescript(_SCHEMA)

    # Seed users
    for uname, pwd, role, name in _DEFAULT_USERS:
        try:
            cur.execute(
                "INSERT INTO users (username, password, role, full_name) VALUES (?,?,?,?)",
                (uname, _hash(pwd), role, name),
            )
        except sqlite3.IntegrityError:
            pass

    # Seed templates only when empty
    cur.execute("SELECT COUNT(*) FROM report_templates")
    if cur.fetchone()[0] == 0:
        _seed_template(cur, "Blood Chemistry Panel",
                       "Standard blood chemistry analysis", _BLOOD_VARS)
        _seed_template(cur, "Urinalysis",
                       "Complete urinalysis panel", _URINE_VARS)
        _seed_template(cur, "Complete Blood Count (CBC)",
                       "CBC with differential", _CBC_VARS)

    conn.commit()
    conn.close()


def _seed_template(cur, name, description, variables):
    cur.execute(
        "INSERT INTO report_templates (name, description, created_by) VALUES (?,?,1)",
        (name, description),
    )
    tid = cur.lastrowid
    for v in variables:
        cur.execute(
            """INSERT INTO template_variables
               (template_id, name, unit, normal_min, normal_max,
                has_status, display_order)
               VALUES (?,?,?,?,?,?,?)""",
            (tid, v[0], v[1], v[2], v[3], v[4], v[5]),
        )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str):
    """Return a dict with user data, or None on failure."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    if row and _verify(password, row["password"]):
        return dict(row)
    return None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def get_templates() -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM report_templates ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_template_variables(template_id: int) -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM template_variables
           WHERE template_id=? ORDER BY display_order""",
        (template_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_template(name: str, description: str, variables: list,
                  created_by: int) -> int:
    """Create a new template and its variables. Returns new template id."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO report_templates (name, description, created_by) VALUES (?,?,?)",
        (name, description, created_by),
    )
    tid = cur.lastrowid
    for i, v in enumerate(variables):
        cur.execute(
            """INSERT INTO template_variables
               (template_id, name, unit, normal_min, normal_max,
                has_status, display_order)
               VALUES (?,?,?,?,?,?,?)""",
            (tid, v.get("name", ""), v.get("unit"), v.get("normal_min"),
             v.get("normal_max"), v.get("has_status", 1), i),
        )
    conn.commit()
    conn.close()
    return tid


# ---------------------------------------------------------------------------
# Reports – create / update
# ---------------------------------------------------------------------------

def create_report(title: str, template_id: int, created_by: int,
                  sample_id: str = "", patient_id: str = "",
                  patient_name: str = "") -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO lab_reports
           (title, template_id, created_by, sample_id, patient_id, patient_name)
           VALUES (?,?,?,?,?,?)""",
        (title, template_id, created_by, sample_id, patient_id, patient_name),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def save_report_values(report_id: int, values: list) -> None:
    """Replace all values for a report.

    Each item in *values* must be a dict with keys:
        variable_name, value, unit, test_status, has_status,
        display_order, normal_range
    """
    conn = _connect()
    conn.execute("DELETE FROM report_values WHERE report_id=?", (report_id,))
    for v in values:
        conn.execute(
            """INSERT INTO report_values
               (report_id, variable_name, value, unit, test_status,
                has_status, display_order, normal_range)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                report_id,
                v.get("variable_name", ""),
                v.get("value", ""),
                v.get("unit", ""),
                v.get("test_status"),
                v.get("has_status", 1),
                v.get("display_order", 0),
                v.get("normal_range", ""),
            ),
        )
    conn.commit()
    conn.close()


def submit_report(report_id: int) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE lab_reports SET status='submitted', submitted_at=? WHERE id=?",
        (datetime.now().isoformat(), report_id),
    )
    conn.commit()
    conn.close()


def audit_report(report_id: int, auditor_id: int,
                 status: str, notes: str = "") -> None:
    conn = _connect()
    conn.execute(
        """UPDATE lab_reports
           SET status=?, audited_by=?, audited_at=?, audit_notes=?
           WHERE id=?""",
        (status, auditor_id, datetime.now().isoformat(), notes, report_id),
    )
    conn.commit()
    conn.close()


def update_report_meta(report_id: int, title: str, sample_id: str,
                       patient_id: str, patient_name: str) -> None:
    conn = _connect()
    conn.execute(
        """UPDATE lab_reports
           SET title=?, sample_id=?, patient_id=?, patient_name=?
           WHERE id=?""",
        (title, sample_id, patient_id, patient_name, report_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Reports – read
# ---------------------------------------------------------------------------

def get_reports_by_user(user_id: int) -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT r.*, u.full_name as tech_name,
                  t.name as template_name
           FROM lab_reports r
           LEFT JOIN users u ON u.id = r.created_by
           LEFT JOIN report_templates t ON t.id = r.template_id
           WHERE r.created_by=?
           ORDER BY r.created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submitted_reports() -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT r.*, u.full_name as tech_name,
                  t.name as template_name
           FROM lab_reports r
           LEFT JOIN users u ON u.id = r.created_by
           LEFT JOIN report_templates t ON t.id = r.template_id
           WHERE r.status='submitted'
           ORDER BY r.submitted_at ASC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_reports() -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT r.*, u.full_name as tech_name,
                  t.name as template_name,
                  a.full_name as auditor_name
           FROM lab_reports r
           LEFT JOIN users u  ON u.id = r.created_by
           LEFT JOIN users a  ON a.id = r.audited_by
           LEFT JOIN report_templates t ON t.id = r.template_id
           ORDER BY r.created_at DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_approved_reports() -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT r.*, u.full_name as tech_name,
                  t.name as template_name
           FROM lab_reports r
           LEFT JOIN users u  ON u.id = r.created_by
           LEFT JOIN report_templates t ON t.id = r.template_id
           WHERE r.status IN ('approved', 'audited')
           ORDER BY r.created_at DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_details(report_id: int):
    conn = _connect()
    row = conn.execute(
        """SELECT r.*, u.full_name as tech_name,
                  a.full_name as auditor_name,
                  t.name as template_name
           FROM lab_reports r
           LEFT JOIN users u  ON u.id = r.created_by
           LEFT JOIN users a  ON a.id = r.audited_by
           LEFT JOIN report_templates t ON t.id = r.template_id
           WHERE r.id=?""",
        (report_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_report_values(report_id: int) -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM report_values WHERE report_id=?
           ORDER BY has_status DESC, display_order""",
        (report_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

def add_attachment(report_id: int, filename: str,
                   filepath: str, file_type: str = "") -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO attachments (report_id, filename, filepath, file_type)
           VALUES (?,?,?,?)""",
        (report_id, filename, filepath, file_type),
    )
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    return aid


def get_attachments(report_id: int) -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM attachments WHERE report_id=? ORDER BY created_at",
        (report_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_attachment(attachment_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def get_all_users() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, username, role, full_name, created_at FROM users ORDER BY role, full_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, password: str, role: str,
                full_name: str) -> bool:
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO users (username, password, role, full_name) VALUES (?,?,?,?)",
            (username, _hash(password), role, full_name),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
