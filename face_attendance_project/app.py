import base64
import hashlib
import secrets
import time
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
import qrcode
from streamlit_js_eval import get_geolocation
import face_recognition

from utils import (
    mark_attendance,
    read_subject,
    get_all_subjects_stats,
    get_subject_stats,
    get_student_attendance_percent,
    get_overall_attendance_for_student,
    haversine_m,
    save_active_session,
    load_active_session,
    clear_active_session,
    load_students,
    save_students,
    delete_student_everywhere,   # <-- make sure this is in your utils.py
)

# ---------------- PATHS ----------------
ROOT = Path(__file__).parent
ENC_FILE = ROOT / "encoded_faces" / "encodings.pkl"
IMAGES_DIR = ROOT / "images"
ASSETS_DIR = ROOT / "assets"
ATT_DIR = ROOT / "attendance_records"

for d in [IMAGES_DIR, ASSETS_DIR, ATT_DIR]:
    d.mkdir(exist_ok=True)

# ---------------- CONFIG ----------------
SUBJECTS = [
    "AI", "DAA", "OS", "COA", "COI",
    "Soft Computing", "UHV", "Biology",
    "OS Lab", "Soft Computing Lab",
]

USERS = {
    "teacher": {
        "password": "Teacher@1234",
        "role": "teacher",
        "display": "Subject Teacher",
    },
    "coordinator": {
        "password": "Coord@1234",
        "role": "coordinator",
        "display": "Class Coordinator",
    },
}

DEFAULT_LAT, DEFAULT_LON = 28.3667, 77.3156  # JC Bose UST Faridabad
SESSION_RADIUS_M = 150
TOKEN_INTERVAL = 30  # seconds

# ---------------- STREAMLIT CONFIG ----------------
st.set_page_config(
    page_title="CEDS Smart Attendance – JC Bose UST",
    layout="wide",
    page_icon="🎓",
    initial_sidebar_state="expanded",
)
# force light theme base, but we style ourselves
st.markdown("<style>:root{color-scheme:light only;}</style>", unsafe_allow_html=True)

# ---------------- GLOBAL STYLE (Glass Blue UI) ----------------
def set_base_style():
    st.markdown(
        """
        <style>
        /* Full background */
        .stApp {
            background: radial-gradient(circle at top left, #1a4bff 0, #050818 45%, #02040c 100%);
            color: #f9fafb;
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        /* Hide Streamlit default header/footer */
        header[data-testid="stHeader"] {background: transparent;}
        footer {visibility: hidden;}

        /* Generic glass card */
        .glass-card {
            background: rgba(5, 12, 40, 0.82);
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 28px 80px rgba(0,0,0,0.70);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            padding: 1.8rem 2.2rem;
        }

        .glass-header {
            font-size: 1.1rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #b3c7ff;
        }

        .brand-main {
            font-size: 1.9rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            color: #ffffff;
            text-shadow: 0 0 18px rgba(23, 138, 255, 0.9);
        }

        .sub-brand {
            color: #d1e4ff;
            font-size: 0.95rem;
        }

        .muted {
            color: #a4b1ff;
            font-size: 0.85rem;
        }

        /* Input styling */
        input, textarea {
            color: #f9fafb !important;
            background-color: rgba(18, 24, 48, 0.95) !important;
            border-radius: 10px !important;
            border: 1px solid rgba(148, 163, 253, 0.5) !important;
        }

        .stTextInput > div > div > input {
            color: #ffffff !important;
        }

        .stPassword > div > div > input {
            color: #ffffff !important;
        }

        /* Select / radio */
        div[data-baseweb="select"] > div {
            background-color: rgba(18, 24, 48, 0.95) !important;
            border-radius: 10px !important;
            border: 1px solid rgba(148, 163, 253, 0.6) !important;
        }

        .stRadio > div {
            justify-content: center;
        }

        /* Buttons */
        .stButton>button {
            background: linear-gradient(135deg, #2563eb, #22c55e);
            color: #f9fafb;
            font-weight: 600;
            border-radius: 999px;
            border: none;
            padding: 0.55rem 1.5rem;
            box-shadow: 0 18px 30px rgba(37, 99, 235, 0.45);
            transition: all 0.18s ease-out;
        }
        .stButton>button:hover {
            background: linear-gradient(135deg, #1d4ed8, #16a34a);
            transform: translateY(-1px) scale(1.02);
            box-shadow: 0 22px 40px rgba(15, 23, 42, 0.85);
        }

        /* Danger button style (for delete student) */
        .danger-btn > button {
            background: linear-gradient(135deg, #ef4444, #f97316) !important;
            box-shadow: 0 18px 30px rgba(220, 38, 38, 0.55) !important;
        }

        /* Metric cards */
        .metric-label {
            font-size: 0.85rem;
            color: #9ca3ff;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #f9fafb;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: rgba(3, 7, 18, 0.96);
            backdrop-filter: blur(22px);
            -webkit-backdrop-filter: blur(22px);
            border-right: 1px solid rgba(148, 163, 253, 0.3);
        }
        section[data-testid="stSidebar"] .css-1d391kg p,
        section[data-testid="stSidebar"] p {
            color: #e5e7eb;
        }

        /* QR image center */
        .qr-wrapper {
            display:flex;
            justify-content:center;
            align-items:center;
            margin-top:0.5rem;
            margin-bottom:0.5rem;
        }

        .warn-text {
            color: #fde68a;
            font-weight: 500;
        }

        .alert-danger {
            background: rgba(248, 113, 113, 0.15);
            border-radius: 10px;
            padding: 0.6rem 0.9rem;
            border: 1px solid rgba(248, 113, 113, 0.6);
            color: #fecaca;
            font-size: 0.85rem;
        }
        .alert-success {
            background: rgba(52, 211, 153, 0.18);
            border-radius: 10px;
            padding: 0.6rem 0.9rem;
            border: 1px solid rgba(52, 211, 153, 0.85);
            color: #bbf7d0;
            font-size: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def js_autorefresh(ms: int = 30000):
    """Simple JS auto refresh (for rotating QR / token)."""
    st.markdown(
        f"""
        <script>
        setInterval(function(){{
            try {{ window.location.reload(); }} catch(e) {{}}
        }}, {ms});
        </script>
        """,
        unsafe_allow_html=True,
    )

# ---------------- ENCODINGS ----------------
@st.cache_data(ttl=300)
def load_encodings():
    import pickle
    if not ENC_FILE.exists():
        return {"encodings": [], "names": []}
    with open(ENC_FILE, "rb") as f:
        return pickle.load(f)

# ---------------- TOKEN HELPERS ----------------
def get_current_period() -> int:
    return int(time.time() // TOKEN_INTERVAL)

def generate_token(secret: str, period: int | None = None) -> str:
    if period is None:
        period = get_current_period()
    return hashlib.sha256(f"{secret}:{period}".encode()).hexdigest()[:8].upper()

def validate_token(secret: str, token_in: str) -> bool:
    if not token_in:
        return False
    token_in = token_in.strip().upper()
    now = get_current_period()
    for p in (now, now - 1):   # allow current + previous 30s window
        if generate_token(secret, p) == token_in:
            return True
    return False

# ---------------- VALIDATION ----------------
def is_college_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.-]+@jcboseust\.ac\.in$", (email or "").strip()))

def validate_student_password(p: str) -> bool:
    # Demo rule: at least 1 upper, 1 lower, 1 special, and 8 digits in a row (DOB)
    return all(
        [
            re.search(r"[A-Z]", p or ""),
            re.search(r"[a-z]", p or ""),
            re.search(r"[^A-Za-z0-9]", p or ""),
            re.search(r"\d{8}", p or ""),
        ]
    )

# ---------------- FACE VERIFY ----------------
def verify_face(known_encs, known_names, uploaded, tolerance: float = 0.55):
    """
    Uses st.camera_input captured frame.
    Returns matched name or None.
    """
    if uploaded is None:
        return None

    try:
        img = Image.open(uploaded).convert("RGB")
        rgb = np.array(img)

        boxes = face_recognition.face_locations(rgb)
        encs = face_recognition.face_encodings(rgb, boxes)

        if not encs:
            return None

        enc = encs[0]
        if len(known_encs) == 0:
            return None

        # distance based
        dists = face_recognition.face_distance(known_encs, enc)
        idx = int(np.argmin(dists))
        if dists[idx] <= tolerance:
            return known_names[idx]
        return None
    except Exception:
        return None

# ---------------- STUDENT REGISTER ----------------
def register_student(name: str, email: str, roll: str, subjects: list[str]):
    if not name.strip():
        return False, "Student name is required."
    if not is_college_email(email):
        return False, "Use official @jcboseust.ac.in email."
    if not roll.strip():
        return False, "University roll number is required."

    students = load_students()
    key = email.strip().lower()
    students[key] = {
        "name": name.strip(),
        "email": email.strip(),
        "roll": roll.strip(),
        "subjects": subjects,
        "created_at": datetime.now().isoformat(),
    }
    save_students(students)
    return True, f"{name} registered/updated successfully."

def student_exists(email: str) -> bool:
    students = load_students()
    return email.strip().lower() in students

# ---------------- SMALL HELPERS ----------------
def show_metric(label: str, value: str | float | int):
    st.markdown(f"<div class='metric-label'>{label}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-value'>{value}</div>", unsafe_allow_html=True)

def get_student_display_name(email: str) -> str:
    students = load_students()
    rec = students.get(email.strip().lower())
    return rec["name"] if rec else email

# ---------------- LANDING PAGE ----------------
def landing_page():
    set_base_style()
    logo = ASSETS_DIR / "logo.png"

    col = st.columns([1, 1, 1])[1]  # center column

    with col:
        st.markdown("<div class='glass-card' style='margin-top:7vh;text-align:center;'>", unsafe_allow_html=True)
        if logo.exists():
            st.image(str(logo), width=120)
        st.markdown(
            "<div class='brand-main'>CEDS SMART ATTENDANCE</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='sub-brand'>JC Bose University of Science & Technology, YMCA Faridabad</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='muted'>Department of Computer Engineering</p>",
            unsafe_allow_html=True,
        )
       

        if st.button("Proceed to Login"):
            st.session_state.page = "login"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------- LOGIN PAGE ----------------
def login_page():
    set_base_style()
    logo = ASSETS_DIR / "logo.png"

    col = st.columns([1, 1, 1])[1]
    with col:
        st.markdown("<div class='glass-card' style='margin-top:7vh;text-align:center;'>", unsafe_allow_html=True)
        if logo.exists():
            st.image(str(logo), width=90)
        st.markdown("<div class='glass-header'>Secure Portal</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0.3rem;'>Login</h3>", unsafe_allow_html=True)

        role = st.radio("Login as", ["Student", "Teacher", "Coordinator"], horizontal=True, key="login_role")

        if role == "Student":
            email = st.text_input("College Email (@jcboseust.ac.in)", key="student_email")
            pw = st.text_input("Password (must contain DOB etc.)", type="password", key="student_pw")

            if st.button("Login as Student", key="student_login_btn"):
                if not is_college_email(email):
                    st.error("Use your official JC Bose college email.")
                elif not validate_student_password(pw):
                    st.error("Password must include DOB format (e.g., Abc@02092003) + mix of characters.")
                elif not student_exists(email):
                    st.error("You are not registered yet. Ask your teacher / coordinator to add you.")
                else:
                    st.session_state.user = email.strip()
                    st.session_state.role = "student"
                    st.session_state.page = "app"
                    st.success("Login successful ✅")
                    st.rerun()

        elif role == "Teacher":
            u = st.text_input("Teacher Username", key="teacher_user")
            p = st.text_input("Password", type="password", key="teacher_pw")
            if st.button("Login as Teacher", key="teacher_login_btn"):
                key = (u or "").strip().lower()
                if key in USERS and USERS[key]["password"] == p and USERS[key]["role"] == "teacher":
                    st.session_state.user = key
                    st.session_state.role = "teacher"
                    st.session_state.page = "app"
                    st.success("Welcome Teacher ✅")
                    st.rerun()
                else:
                    st.error("Invalid teacher credentials.")

        else:  # Coordinator
            u = st.text_input("Coordinator Username", key="coord_user")
            p = st.text_input("Password", type="password", key="coord_pw")
            if st.button("Login as Coordinator", key="coord_login_btn"):
                key = (u or "").strip().lower()
                if key in USERS and USERS[key]["password"] == p and USERS[key]["role"] == "coordinator":
                    st.session_state.user = key
                    st.session_state.role = "coordinator"
                    st.session_state.page = "app"
                    st.success("Welcome Coordinator ✅")
                    st.rerun()
                else:
                    st.error("Invalid coordinator credentials.")

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------- STUDENT VIEWS ----------------
def student_mark_attendance(known_enc, known_names):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Mark Attendance")

    sess = load_active_session()
    if not sess:
        st.warning("No active attendance session. Ask your subject teacher to start one.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    now = datetime.now().time()
    s = datetime.strptime(sess["start"], "%H:%M:%S").time()
    e = datetime.strptime(sess["end"], "%H:%M:%S").time()
    if not (s <= now <= e):
        st.error("Attendance window is closed for the current session.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.success(
        f"Active Session: **{sess['subject']}**  "
        f"({sess['start']} – {sess['end']})"
    )

    st.markdown("##### Step 1 · Token Verification")
    token_in = st.text_input("Enter 8-character Token shown in QR", key="student_token_input")

    if st.button("Verify Token", key="verify_token_btn"):
        if validate_token(sess["secret"], token_in):
            st.session_state.token_ok = True
            st.success("Token verified ✅ Proceed to face verification.")
        else:
            st.session_state.token_ok = False
            st.error("Invalid or expired token. Use the latest QR from teacher screen.")

    st.caption("Token rotates every 30 seconds. If you get error, wait a moment and check new QR.")
    js_autorefresh(30000)

    if st.session_state.get("token_ok"):
        st.markdown("---")
        st.markdown("##### Step 2 · Live Face Verification")
        frame = st.camera_input("Align your face clearly in the box and click **Capture**", key="student_camera")

        if frame is not None:
            name = verify_face(known_enc, known_names, frame, tolerance=0.55)
            if not name:
                st.markdown(
                    "<div class='alert-danger'>Face not recognized. Try again with clear lighting or contact your teacher.</div>",
                    unsafe_allow_html=True,
                )
                st.session_state.token_ok = False
                st.markdown("</div>", unsafe_allow_html=True)
                return

            # Location check (if available)
            loc = get_geolocation()
            lat = lon = None
            if loc and "coords" in loc:
                lat = loc["coords"].get("latitude")
                lon = loc["coords"].get("longitude")

            if lat is not None and lon is not None:
                dist = haversine_m(lat, lon, sess["center_lat"], sess["center_lon"])
                if dist > sess["radius_m"]:
                    st.markdown(
                        f"<div class='alert-danger'>You are outside allowed campus/class radius (~{int(dist)} m). Attendance denied.</div>",
                        unsafe_allow_html=True,
                    )
                    st.session_state.token_ok = False
                    st.markdown("</div>", unsafe_allow_html=True)
                    return

            ok = mark_attendance(
                name=name,
                subject=sess["subject"],
                lat=lat,
                lon=lon,
                source="student",
                token_used=token_in,
            )
            if ok:
                st.markdown(
                    f"<div class='alert-success'>Attendance marked successfully for <b>{name}</b> ✅</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Your attendance is already marked for today for this subject.")
            st.session_state.token_ok = False

    st.markdown("</div>", unsafe_allow_html=True)


def student_subject_attendance(email: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("My Subject-wise Attendance")
    stats = get_student_attendance_percent(email)
    if not stats:
        st.info("No attendance data found yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df = pd.DataFrame(
        [{"Subject": s, "Percentage": p} for s, p in stats.items()]
    ).sort_values("Subject")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("##### Bar Chart")
    chart_df = df.set_index("Subject")
    st.bar_chart(chart_df)

    st.markdown("</div>", unsafe_allow_html=True)


def student_overall_attendance(email: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Overall Attendance")

    overall = get_overall_attendance_for_student(email)
    stats = get_student_attendance_percent(email)

    c1, c2 = st.columns(2)
    with c1:
        if overall is None:
            show_metric("Overall Attendance", "NA")
        else:
            show_metric("Overall Attendance", f"{overall:.2f}%")
    with c2:
        count_subjects = len(stats) if stats else 0
        show_metric("Subjects with Attendance", count_subjects)

    if overall is not None and overall < 75:
        st.markdown(
            "<p class='warn-text'>Alert: Your overall attendance is below 75%. "
            "You may be detained from exams. Please attend more classes.</p>",
            unsafe_allow_html=True,
        )

    if stats:
        df = pd.DataFrame(
            [{"Subject": s, "Percentage": p} for s, p in stats.items()]
        ).sort_values("Subject")
        st.markdown("##### Subject-wise %")
        st.bar_chart(df.set_index("Subject"))

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- TEACHER VIEWS ----------------
def teacher_dashboard(subject: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader(f"Dashboard – {subject}")

    df = read_subject(subject)
    stats = get_subject_stats(subject)

    c1, c2, c3 = st.columns(3)
    total_records = len(df)
    unique_students = df["Name"].nunique() if not df.empty else 0
    avg_att = stats["Percentage"].mean() if not stats.empty else 0

    with c1:
        show_metric("Total Attendance Records", total_records)
    with c2:
        show_metric("Unique Students", unique_students)
    with c3:
        show_metric("Average Attendance %", f"{avg_att:.1f}%")

    if not stats.empty:
        st.markdown("##### Attendance Distribution")
        st.bar_chart(stats.set_index("Name")["Percentage"])

    st.markdown("</div>", unsafe_allow_html=True)


def teacher_start_session(selected_subject: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader(f"Start Attendance Session – {selected_subject}")

    start_time = st.time_input("Start Time", datetime.now().time(), key="sess_start")
    end_time = st.time_input(
        "End Time",
        (datetime.now() + timedelta(minutes=10)).time(),
        key="sess_end",
    )

    if st.button("Start Session", key="start_session_btn"):
        secret = secrets.token_hex(8)
        data = {
            "subject": selected_subject,
            "start": start_time.strftime("%H:%M:%S"),
            "end": end_time.strftime("%H:%M:%S"),
            "secret": secret,
            "center_lat": DEFAULT_LAT,
            "center_lon": DEFAULT_LON,
            "radius_m": SESSION_RADIUS_M,
            "created_by": st.session_state.user,
            "created_at": datetime.now().isoformat(),
        }
        save_active_session(data)
        st.success("Session started ✅ QR token will auto-rotate every 30 seconds.")
        st.rerun()

    sess = load_active_session()
    if sess:
        st.markdown("---")
        st.info(
            f"Active Session: **{sess['subject']}** "
            f"({sess['start']} – {sess['end']})"
        )
        token = generate_token(sess["secret"])
        qr = qrcode.make(token)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        st.markdown("<div class='qr-wrapper'>", unsafe_allow_html=True)
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' width='190'/>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.code(f"Current Token: {token}", language="bash")
        st.caption("QR / token refresh automatically every 30 seconds.")
        js_autorefresh(30000)

        if st.button("End Session", key="end_session_btn"):
            clear_active_session()
            st.warning("Session ended.")
            st.rerun()
    else:
        st.warning("No active session currently.")

    st.markdown("</div>", unsafe_allow_html=True)


def teacher_view_subject_attendance(selected_subject: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader(f"Attendance Records – {selected_subject}")

    df = read_subject(selected_subject)
    if df.empty:
        st.info("No attendance data yet for this subject.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Filters
    with st.expander("Filters", expanded=False):
        date_from = st.date_input("From date", key="sub_filter_from")
        date_to = st.date_input("To date", key="sub_filter_to")
        name_filter = st.text_input("Search by Student Name / Email / Roll (partial)", key="sub_name_filter")

        if date_from and date_to:
            df = df[
                (df["Date"] >= pd.to_datetime(date_from).date().isoformat())
                & (df["Date"] <= pd.to_datetime(date_to).date().isoformat())
            ]
        if name_filter.strip():
            patt = name_filter.strip().lower()
            df = df[
                df["Name"].str.lower().str.contains(patt)
                | df["Email"].str.lower().str.contains(patt)
                | df["Roll"].astype(str).str.lower().str.contains(patt)
            ]

    st.dataframe(df, use_container_width=True, hide_index=True)

    stats = get_subject_stats(selected_subject)
    if not stats.empty:
        st.markdown("##### Summary")
        st.dataframe(stats, use_container_width=True, hide_index=True)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False),
            file_name=f"{selected_subject}_attendance.csv",
            mime="text/csv",
            key="download_subject_csv",
        )

    st.markdown("</div>", unsafe_allow_html=True)


def teacher_register_student(selected_subject: str):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Register / Update Student")

    name = st.text_input("Student Name", key="reg_name")
    email = st.text_input("College Email (@jcboseust.ac.in)", key="reg_email")
    roll = st.text_input("University Roll No.", key="reg_roll")
    subs = st.multiselect("Subjects for this student", SUBJECTS, default=[selected_subject], key="reg_subjects")

    if st.button("Save Student", key="reg_save_btn"):
        ok, msg = register_student(name, email, roll, subs)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.markdown("</div>", unsafe_allow_html=True)


def teacher_delete_student():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Delete Student (Everywhere)")

    st.markdown(
        "<p class='muted'>This will remove the student from <b>students.json</b> "
        "and delete their attendance across <b>all subjects</b>. Use carefully.</p>",
        unsafe_allow_html=True,
    )

    email = st.text_input("Student College Email (@jcboseust.ac.in)", key="del_email")
    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Delete Student", key="del_btn", use_container_width=True):
            if not is_college_email(email):
                st.error("Enter a valid official college email.")
            else:
                ok, msg = delete_student_everywhere(email, SUBJECTS)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- COORDINATOR VIEWS ----------------
def coordinator_dashboard():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Coordinator Dashboard – All Subjects")

    stats = get_all_subjects_stats()
    if stats.empty:
        st.info("No attendance data available yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    total_records = stats["Total Records"].sum()
    avg_att = stats["Percentage"].mean()
    num_subjects = len(stats)

    c1, c2, c3 = st.columns(3)
    with c1:
        show_metric("Total Records", total_records)
    with c2:
        show_metric("Subjects", num_subjects)
    with c3:
        show_metric("Average Attendance %", f"{avg_att:.1f}%")

    st.markdown("##### Subject-wise Attendance %")
    st.bar_chart(stats.set_index("Subject")["Percentage"])

    st.markdown("</div>", unsafe_allow_html=True)


def coordinator_register_student():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Register / Update Student")

    name = st.text_input("Student Name", key="coord_reg_name")
    email = st.text_input("College Email (@jcboseust.ac.in)", key="coord_reg_email")
    roll = st.text_input("University Roll No.", key="coord_reg_roll")
    subs = st.multiselect("Subjects", SUBJECTS, key="coord_reg_subjects")

    if st.button("Save Student", key="coord_reg_save_btn"):
        ok, msg = register_student(name, email, roll, subs)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- MAIN APP ROUTER ----------------
def main_app():
    set_base_style()

    enc = load_encodings()
    known_enc, known_names = enc.get("encodings", []), enc.get("names", [])

    # Header
    top_l, top_r = st.columns([5, 1])
    with top_l:
        user_disp = get_student_display_name(st.session_state.user) if st.session_state.role == "student" else st.session_state.user
        st.markdown(
            f"<div class='glass-header' style='margin-bottom:0;'>Welcome, {st.session_state.role.capitalize()}</div>"
            f"<h2 style='margin-top:0.2rem;'>"
            f"{user_disp if isinstance(user_disp, str) else st.session_state.user}</h2>",
            unsafe_allow_html=True,
        )
    with top_r:
        if st.button("Logout", key="logout_btn"):
            for k in ["user", "role", "page", "token_ok"]:
                st.session_state.pop(k, None)
            st.session_state.page = "landing"
            st.rerun()

    role = st.session_state.role

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### Navigation")
        if role == "student":
            choice = st.selectbox(
                "Select Action",
                ["Mark Attendance", "My Subject-wise Attendance", "My Overall Attendance", "Logout"],
                key="student_choice",
            )
        elif role == "teacher":
            subject = st.selectbox("Select Subject", SUBJECTS, key="teacher_subject")
            st.session_state.selected_subject = subject
            choice = st.selectbox(
                "Select Action",
                [
                    "Dashboard",
                    "Start Attendance Session",
                    "View Subject Attendance",
                    "Register / Update Student",
                    "Delete Student",
                    "Logout",
                ],
                key="teacher_choice",
            )
        elif role == "coordinator":
            choice = st.selectbox(
                "Select Action",
                ["Dashboard", "Register / Update Student", "Logout"],
                key="coord_choice",
            )
        else:
            choice = "Logout"

    # ---- STUDENT ----
    if role == "student":
        email = st.session_state.user
        if choice == "Mark Attendance":
            student_mark_attendance(known_enc, known_names)
        elif choice == "My Subject-wise Attendance":
            student_subject_attendance(email)
        elif choice == "My Overall Attendance":
            student_overall_attendance(email)
        elif choice == "Logout":
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("### Thank you for using CEDS Smart Attendance 🙌")
            if st.button("Back to Welcome", key="student_back_home"):
                for k in ["user", "role", "page", "token_ok"]:
                    st.session_state.pop(k, None)
                st.session_state.page = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ---- TEACHER ----
    elif role == "teacher":
        selected_subject = st.session_state.get("selected_subject", SUBJECTS[0])

        if choice == "Dashboard":
            teacher_dashboard(selected_subject)
        elif choice == "Start Attendance Session":
            teacher_start_session(selected_subject)
        elif choice == "View Subject Attendance":
            teacher_view_subject_attendance(selected_subject)
        elif choice == "Register / Update Student":
            teacher_register_student(selected_subject)
        elif choice == "Delete Student":
            teacher_delete_student()
        elif choice == "Logout":
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("### Thank you, Teacher 🙏")
            if st.button("Back to Welcome", key="teacher_back_home"):
                for k in ["user", "role", "page", "token_ok"]:
                    st.session_state.pop(k, None)
                st.session_state.page = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ---- COORDINATOR ----
    elif role == "coordinator":
        if choice == "Dashboard":
            coordinator_dashboard()
        elif choice == "Register / Update Student":
            coordinator_register_student()
        elif choice == "Logout":
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("### Thank you, Coordinator 🙏")
            if st.button("Back to Welcome", key="coord_back_home"):
                for k in ["user", "role", "page", "token_ok"]:
                    st.session_state.pop(k, None)
                st.session_state.page = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ---------------- ENTRY ROUTER ----------------
if "page" not in st.session_state:
    st.session_state.page = "landing"

if st.session_state.page == "landing":
    landing_page()
elif st.session_state.page == "login":
    login_page()
else:
    if not st.session_state.get("user"):
        st.session_state.page = "login"
        login_page()
    else:
        main_app()
