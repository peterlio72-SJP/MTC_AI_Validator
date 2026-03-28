import streamlit as st
import google.generativeai as genai

# This line links your secret key to the AI engine
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("API Key not found in Streamlit Secrets!")
import streamlit as st
import pandas as pd

# --- Professional UI Setup ---
st.set_page_config(page_title="MTC AI Validator Pro", layout="wide")

# Hide Streamlit branding
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: ENGINEERING SELECTIONS ---
with st.sidebar:
    st.header("⚙️ Design Criteria")
    
    # Selection 1: Engineering Code
    eng_code = st.selectbox(
        "Application Category",
        ["Pressure Parts (ASME Sec VIII/B31.3)", "Structural Steel (AWS D1.1)", "General Construction"]
    )
    
    # Selection 2: Material Grade Selection
    if eng_code == "Pressure Parts (ASME Sec VIII/B31.3)":
        target_material = st.selectbox("Select ASTM Grade", ["A106 Gr. B", "A516 Gr. 65", "A105N", "A333 Gr. 6"])
    else:
        target_material = st.selectbox("Select Structural Grade", ["Q355D", "S355J2", "A992", "Q235B"])
    
    # Selection 3: Sour Service Toggle
    sour_service = st.toggle("NACE MR0175 / Sour Service", help="Reduces Hardness limit to 22 HRC / 237 HBW")
    
    st.divider()
    st.info(f"Reviewing for: *{eng_code}*")

# --- MAIN SCREEN ---
st.title("🏗️ Engineering MTC Validator")
st.write(f"Validating document against *{target_material}* requirements.")

uploaded_file = st.file_uploader("Drop MTC File", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    # AUTOMATED LOGIC
    with st.spinner("Processing..."):
        
        # Hardness Logic based on selection
        limit_hbw = 237 if sour_service else 280
        
        # CE Limit (Carbon Equivalent)
        ce_limit = 0.43 if "355" in target_material or "516" in target_material else 0.45
        
        st.success(f"File Received: {uploaded_file.name}")
        
        # Results Display Table
        results_data = {
            "QC Parameter": ["Hardness Limit", "Max Carbon Equivalent (CE)", "Heat Treatment", "Material Group"],
            "Requirement": [f"≤ {limit_hbw} HBW", f"≤ {ce_limit}", "Normalized" if sour_service else "As-Rolled/Any", "P-No 1 / Group II"],
            "Found on MTC": ["Extracting...", "Calculating...", "Detecting...", "Detecting..."],
            "Status": ["⏳", "⏳", "⏳", "⏳"]
        }
        
        st.subheader("📊 Automated Compliance Summary")
        st.table(pd.DataFrame(results_data))
        
        if sour_service:
            st.warning("⚠️ CRITICAL: Hardness values must be verified per NACE MR0175 Table A.2.")
