
import streamlit as st
import pandas as pd
import joblib
import base64
import matplotlib.pyplot as plt
from sklearn.preprocessing import LabelEncoder
from fpdf import FPDF
import io

# Load models
model = joblib.load("rf_model_clean_10k.joblib")
salary_model = joblib.load("salary_model_10k.joblib")

# Config
st.set_page_config(page_title="Campus Placement Predictor", layout="wide")

def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

img_base64 = get_base64_image("placement_banner3.jpg")

# Styling
st.markdown(f"""
<style>
.stApp {{
    background-image: url("data:image/jpg;base64,{img_base64}");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;
}}
.title {{ text-align: center; font-size: 42px; font-weight: bold; color: black; margin-top: 100px; }}
.subtitle {{ text-align: center; font-size: 20px; color: black; margin-bottom: 25px; }}
.login-container {{ display: flex; justify-content: center; }}
.stNumberInput input, .stSelectbox div, .stSlider, .stRadio, .stTextInput input, .stButton button {{
    background-color: white !important; color: black !important;
}}
.credit {{ position: fixed; bottom: 10px; right: 20px; font-size: 13px; color: black; }}
.quote {{ text-align: center; font-size: 16px; color: #222; margin-top: 20px; font-style: italic; }}
</style>
<div class="credit">App by Deeksha Dhatterwal</div>
""", unsafe_allow_html=True)

# Session state
for key in ["page", "role", "exit", "result", "input_data", "salary", "name", "original_branch"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "exit" else False

# Exit Page
if st.session_state.exit:
    st.markdown('<div class="title">Thank you for using the Campus Placement Predictor!</div>', unsafe_allow_html=True)
    st.markdown('<div class="quote">“Opportunities don’t happen. You create them.” – Chris Grosser</div>', unsafe_allow_html=True)
    st.subheader("💬 Placement Chatbot")

    def get_bot_reply(user_input):
        u = user_input.lower()
        if "placement" in u: return "Campus placement depends on CGPA, skills, projects, and internships."
        elif "salary" in u: return "Salary depends on placement status, skills, and the company profile."
        elif "improve" in u: return "Focus on upskilling, doing internships, and communication skills."
        elif "skills" in u: return "Python, Data Structures, Communication, and Teamwork are key."
        return "I'm still learning. Try asking about placement, skills, or salary."

    user_input = st.text_input("You:", key="chatbot_input")
    if user_input:
        st.text_area("Bot:", value=get_bot_reply(user_input), height=100, key="chatbot_reply")
    st.stop()

# Home Page
if st.session_state.page == "home" or st.session_state.page is None:
    st.session_state.page = "home"
    st.markdown('<div class="title">Campus Placement Predictor</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">🎓 Welcome! This app helps you predict placements or view analytics based on student data.</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    role = st.selectbox(" Select Role to Continue", ["Select...", "Student", "Placement Officer"])
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Login"):
        st.session_state.role = role
        if role == "Student":
            st.session_state.page = "form"
        elif role == "Placement Officer":
            st.session_state.page = "dashboard"
        st.rerun()

# Student Form Page
if st.session_state.page == "form":
    st.markdown('<div class="title"> Student Placement Prediction Form</div>', unsafe_allow_html=True)
    name = st.text_input("Full Name")
    email = st.text_input("Email Address")
    university = st.text_input("University Name")
    school_10 = st.text_input("10th School Name")
    school_12 = st.text_input("12th School Name")

    major_projects = st.radio("Major Project Done?", [0, 1], format_func=lambda x: "Yes" if x else "No")
    major_project_title = st.text_input("Major Project Title") if major_projects == 1 else ""

    minor_projects = st.slider("Mini Projects", 0, 5, 1)
    minor_project_title = st.text_input("Minor Project Title") if minor_projects > 0 else ""

    cgpa = st.number_input("CGPA", 6.0, 10.0)
    skills = st.slider("Skills (1–10)", 1, 10, 7)
    comm = st.slider("Communication Skill Rating (1–5)", 1.0, 5.0, 4.0)

    intern = st.radio("Internship?", [0, 1], format_func=lambda x: "Yes" if x else "No")
    internship_role = st.text_input("Internship Role") if intern == 1 else ""
    internship_company = st.text_input("Internship Company") if intern == 1 else ""
    internship_duration = st.text_input("Internship Duration") if intern == 1 else ""

    hackathon = st.radio("Hackathon?", [0, 1], format_func=lambda x: "Yes" if x else "No")
    perc_12 = st.slider("12th %", 50, 100, 75)
    perc_10 = st.slider("10th %", 50, 100, 80)
    backlogs = st.slider("Backlogs", 0, 7, 1)
    branch = st.selectbox("Branch", ["CSE", "IT", "ECE", "EEE", "Mechanical", "Civil", "Other"])

    if st.button("Predict"):
        st.session_state.name = name
        st.session_state.original_branch = branch
        new_data = pd.DataFrame([{
            'Name': name,
            'CGPA': cgpa,
            'Major Projects': major_projects,
            'Workshops/Certificatios': 2,
            'Mini Projects': minor_projects,
            'Skills': skills,
            'Communication Skill Rating': comm,
            'Internship': intern,
            'Hackathon': hackathon,
            '12th Percentage': perc_12,
            '10th Percentage': perc_10,
            'backlogs': backlogs,
            'Branch': branch
        }])
        le = LabelEncoder()
        new_data['Branch'] = le.fit_transform(new_data['Branch'])
        model_input = new_data.drop(columns=["Name"])
        prob = model.predict_proba(model_input)[0][1]
        salary = int(salary_model.predict(model_input)[0]) if prob >= 0.65 else None
        result = (
            f"✅ Likely Placed (Confidence: {round(prob * 100, 2)}%)" if prob >= 0.75 else
            f" Maybe Placed (Confidence: {round(prob * 100, 2)}%)" if prob >= 0.5 else
            f"❌ Not Placed (Confidence: {round(prob * 100, 2)}%)"
        )
        st.session_state.result = result
        st.session_state.salary = salary
        st.session_state.input_data = new_data
        st.session_state.resume_info = {
            "Email": email,
            "University": university,
            "10th School": school_10,
            "12th School": school_12,
            "Major Project Title": major_project_title,
            "Minor Project Title": minor_project_title,
            "Internship Role": internship_role,
            "Internship Company": internship_company,
            "Internship Duration": internship_duration
        }
        st.session_state.page = "result"
        st.rerun()

# Result Page
if st.session_state.page == "result":
    st.markdown('<div class="title">🎯 Prediction Result</div>', unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: red;'>{st.session_state.result}</h3>", unsafe_allow_html=True)

    df = st.session_state.input_data.copy()
    model_input = df.drop(columns=["Name"])
    result_data = df.copy()
    result_data["Placement Prediction"] = st.session_state.result
    result_data["Predicted Salary"] = st.session_state.salary if st.session_state.salary else "N/A"

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📩 Download Result (CSV)", data=result_data.to_csv(index=False).encode(), file_name="placement_result.csv", mime="text/csv")

    with col2:
        class PDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 16)
                self.cell(0, 10, " Resume", ln=1, align="C")
                self.ln(5)

            def add_section(self, title):
                self.set_font("Arial", "B", 14)
                self.cell(0, 10, title, ln=1)
                self.set_draw_color(0, 0, 0)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(2)

            def add_item(self, label, value):
                self.set_font("Arial", "", 12)
                self.multi_cell(0, 8, f"{label}: {value}")

        info = st.session_state.resume_info
        pdf = PDF()
        pdf.add_page()
        pdf.add_section("Personal Information")
        pdf.add_item("Name", st.session_state.name)
        pdf.add_item("Email", info["Email"])
        pdf.add_item("University", info["University"])
        pdf.add_item("10th School", info["10th School"])
        pdf.add_item("12th School", info["12th School"])

        pdf.add_section("Academic Details")
        pdf.add_item("Branch", st.session_state.original_branch)
        pdf.add_item("CGPA", str(df['CGPA'].iloc[0]))
        pdf.add_item("10th %", str(df['10th Percentage'].iloc[0]))
        pdf.add_item("12th %", str(df['12th Percentage'].iloc[0]))
        pdf.add_item("Backlogs", str(df['backlogs'].iloc[0]))

        pdf.add_section("Projects")
        if info["Major Project Title"]:
            pdf.add_item("Major Project", info["Major Project Title"])
        if info["Minor Project Title"]:
            pdf.add_item("Minor Project", info["Minor Project Title"])

        pdf.add_section("Skills")
        pdf.add_item("Technical Skills", str(df['Skills'].iloc[0]))
        pdf.add_item("Communication", str(df['Communication Skill Rating'].iloc[0]))

        pdf.add_section("Internship")
        if df['Internship'].iloc[0]:
            pdf.add_item("Role", info['Internship Role'])
            pdf.add_item("Company", info['Internship Company'])
            pdf.add_item("Duration", info['Internship Duration'])

        pdf_data = pdf.output(dest='S').encode('latin1')
        st.download_button("📄 Download Resume (PDF)", data=pdf_data, file_name="professional_resume.pdf", mime="application/pdf")

    if st.session_state.salary is not None:
        st.markdown(f"###  Predicted Salary: ₹ {st.session_state.salary:,}")

    with st.expander("📊 Feature Importance Analysis"):
        if hasattr(model, "feature_importances_"):
            feat_imp = pd.Series(model.feature_importances_, index=model_input.columns)
            sorted_imp = feat_imp.sort_values(ascending=False)
            st.bar_chart(sorted_imp)
            st.dataframe(sorted_imp.rename("Importance").apply(lambda x: round(x * 100, 2)).to_frame())

    col3, col4 = st.columns(2)
    with col3:
        st.button("🏠 Go Home", on_click=lambda: st.session_state.update({"page": "home"}))
    with col4:
        st.button("❌ Exit", on_click=lambda: st.session_state.update({"exit": True}))

# Officer Dashboard
if st.session_state.page == "dashboard":
    st.markdown('<div class="title">📊 Placement Officer Dashboard</div>', unsafe_allow_html=True)
    try:
        df = pd.read_csv("/Users/deekshadhatterwal/Downloads/internship_placement_super_9999.csv")
        st.success("AVG, MAX, MIN Analysis for All Features")
        for col in df.select_dtypes(include='number').columns:
            st.markdown(f"**📌 {col}**")
            st.write(f"Avg: `{round(df[col].mean(), 2)}` | Max: `{df[col].max()}` | Min: `{df[col].min()}`")
            st.bar_chart(df[col])
            st.markdown("---")
    except Exception as e:
        st.error("⚠️ Error loading dataset.")
    st.button("🔙 Back to Home", on_click=lambda: st.session_state.update({"page": "home", "role": None}))