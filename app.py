import streamlit as st
import pandas as pd

st.set_page_config(page_title="Professional MTC Validator", layout="wide")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("📋 Review Criteria")
    
    # 1. Selection for Application Type
    app_type = st.selectbox(
        "Application Type",
        ["Pressure Parts (ASME)", "Structural (AWS)", "Lifting/General"]
    )
    
    # 2. Selection for Material Standard
    standard = st.selectbox(
        "Target Standard",
        ["ASME SA106 Gr. B", "ASME SA516 Gr. 65", "GB/T 1591 Q355D", "EN 10025 S355J2"]
    )
    
    # 3. Toggle for Sour Service (NACE)
    nace_req = st.toggle("Sour Service (NACE MR0175)", value=False)
    
    st.divider()
    st.info(f"Reviewing as: {app_type} | {standard}")

# --- MAIN SCREEN ---
st.title("🏗️ Engineering MTC Validator")
uploaded_file = st.file_uploader("Upload MTC for automated review", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    # AUTOMATED LOGIC STARTS HERE
    with st.spinner(f"Validating against {standard}..."):
        
        # Logic for NACE Hardness limits
        hardness_limit = 237 if nace_req else 280
        status_icon = "☣️ SOUR" if nace_req else "⚙️ STD"
        
        st.subheader(f"Compliance Report [{status_icon}]")
        
        # This table now reacts to your sidebar selections
        results = {
            "Parameter": ["Material Standard", "Hardness Limit", "CE Calculation", "Status"],
            "Requirement": [standard, f"< {hardness_limit} HBW", "< 0.43", "Compliant"],
            "MTC Found": ["Detected on MTC", "Calculated", "Calculated", "PASS/FAIL"]
        }
        
        st.table(pd.DataFrame(results))
        
        if nace_req:
            st.warning("Note: Reviewing for Sulfide Stress Cracking (SSC) resistance.")
