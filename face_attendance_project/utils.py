import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import os

ROOT = Path(__file__).parent
STUDENTS_FILE = ROOT / "students.json"
SESSION_FILE = ROOT / "active_session.json"
ATT_DIR = ROOT / "attendance_records"

ATT_DIR.mkdir(exist_ok=True)


# ------------------- STUDENTS -------------------
def load_students():
    if not STUDENTS_FILE.exists():
        return {}
    with open(STUDENTS_FILE, "r") as f:
        return json.load(f)


def save_students(data):
    with open(STUDENTS_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ------------------- ACTIVE SESSION -------------------
def save_active_session(data: dict):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_active_session():
    if not SESSION_FILE.exists():
        return None
    with open(SESSION_FILE, "r") as f:
        return json.load(f)


def clear_active_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


# ------------------- SUBJECT ATTENDANCE FILE -------------------
def subject_file(subject: str) -> Path:
    safe = subject.replace(" ", "_")
    return ATT_DIR / f"{safe}.csv"


def read_subject(subject: str) -> pd.DataFrame:
    fp = subject_file(subject)
    if not fp.exists():
        return pd.DataFrame(
            columns=["Name", "Email", "Roll", "Date", "Time", "Latitude", "Longitude", "Source", "Token"]
        )
    df = pd.read_csv(fp)
    return df


def write_subject(subject: str, df: pd.DataFrame):
    fp = subject_file(subject)
    df.to_csv(fp, index=False)


# ------------------- MARK ATTENDANCE -------------------
def mark_attendance(
    name: str,
    subject: str,
    lat=None,
    lon=None,
    source="student",
    token_used=None
):
    df = read_subject(subject)

    today = datetime.now().date().isoformat()
    already = df[(df["Name"] == name) & (df["Date"] == today)]
    if len(already) > 0:
        return False  # Already marked today

    students = load_students()
    email = None
    roll = None

    # find student email
    for e, data in students.items():
        if data["name"] == name:
            email = e
            roll = data["roll"]
            break

    new = {
        "Name": name,
        "Email": email if email else "",
        "Roll": roll if roll else "",
        "Date": today,
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Latitude": lat,
        "Longitude": lon,
        "Source": source,
        "Token": token_used,
    }

    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    write_subject(subject, df)
    return True


# ------------------- SUBJECT STATISTICS -------------------
def get_subject_stats(subject: str):
    df = read_subject(subject)
    if df.empty:
        return pd.DataFrame(columns=["Name", "Present Count", "Percentage"])

    students = load_students()

    stats_list = []
    for email, data in students.items():
        if subject not in data.get("subjects", []):
            continue
        name = data["name"]
        rec = df[df["Name"] == name]
        total_days = df["Date"].nunique()
        present_days = rec["Date"].nunique()
        percent = (present_days / total_days * 100) if total_days > 0 else 0
        stats_list.append({
            "Name": name,
            "Email": email,
            "Present Count": present_days,
            "Percentage": percent
        })

    return pd.DataFrame(stats_list).sort_values("Percentage", ascending=False)


# ------------------- ALL SUBJECTS STATS (COORDINATOR) -------------------
def get_all_subjects_stats():
    rows = []
    for fp in ATT_DIR.glob("*.csv"):
        subject = fp.stem.replace("_", " ")
        df = pd.read_csv(fp)
        if df.empty:
            rows.append({
                "Subject": subject,
                "Total Records": 0,
                "Present Students": 0,
                "Percentage": 0
            })
            continue

        total = len(df)
        unique = df["Name"].nunique()
        stats = get_subject_stats(subject)
        avg = stats["Percentage"].mean() if not stats.empty else 0

        rows.append({
            "Subject": subject,
            "Total Records": total,
            "Present Students": unique,
            "Percentage": avg
        })

    return pd.DataFrame(rows)


# ------------------- STUDENT SUBJECT-WISE PERCENT -------------------
def get_student_attendance_percent(email: str):
    email = email.lower()
    students = load_students()
    if email not in students:
        return {}

    enrolled = students[email].get("subjects", [])
    name = students[email]["name"]

    results = {}

    for subject in enrolled:
        df = read_subject(subject)
        if df.empty:
            results[subject] = 0
            continue

        total_days = df["Date"].nunique()
        pres = df[df["Name"] == name]["Date"].nunique()
        pct = (pres / total_days * 100) if total_days > 0 else 0
        results[subject] = pct

    return results


# ------------------- STUDENT OVERALL -------------------
def get_overall_attendance_for_student(email: str):
    stats = get_student_attendance_percent(email)
    if not stats:
        return None
    return sum(stats.values()) / len(stats)


# ------------------- DELETE STUDENT EVERYWHERE -------------------
def delete_student_everywhere(email: str, subjects: list[str]):
    email = email.lower()
    students = load_students()

    if email not in students:
        return False, "Student does not exist in records."

    name = students[email]["name"]

    # Remove from students.json
    students.pop(email, None)
    save_students(students)

    # Remove attendance from ALL subjects
    removed_any = False
    for subject in subjects:
        fp = subject_file(subject)
        if not fp.exists():
            continue

        df = pd.read_csv(fp)
        before = len(df)
        df = df[df["Email"].str.lower() != email]
        write_subject(subject, df)

        if len(df) != before:
            removed_any = True

    msg = f"Deleted {name} from database and removed attendance from all subjects."
    return True, msg


# ------------------- GEO DISTANCE -------------------
from math import radians, sin, cos, sqrt, atan2

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
