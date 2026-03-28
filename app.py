
       import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. AI CONFIGURATION ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("Missing API Key in Secrets!")

st.set_page_config(page_title="MTC AI Validator Pro", layout="wide")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Design Criteria")
    eng_code = st.selectbox("Application Category", ["Pressure Parts (ASME)", "Structural Steel (AWS)"])
    target_material = st.selectbox("Select Grade", ["Q355D", "S355J2", "A106 Gr. B", "A516 Gr. 65"])
    sour_service = st.toggle("NACE MR0175 / Sour Service")

# --- 3. MAIN UI ---
st.title("🏗️ Engineering MTC Validator")
uploaded_file = st.file_uploader("Drop MTC File (PDF or Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI is reviewing compliance..."):
        try:
            # Prepare the Model
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Convert file for AI
            file_data = uploaded_file.read()
            mime_type = "application/pdf" if uploaded_file.name.endswith('.pdf') else "image/jpeg"
            
            # The Prompt: Telling AI what to look for based on your buttons
            prompt = f"""
            Review this MTC for {target_material} ({eng_code}). 
            Sour Service requirement: {sour_service}.
            Extract values for:
            - Hardness (Max value found)
            - Carbon Equivalent (CE)
            - Heat Treatment (Normalized/As-Rolled)
            - Material Group (P-Number)
            Return ONLY a table-friendly format.
            """
            
            # Call AI
            response = model.generate_content([prompt, {"mime_type": mime_type, "data": file_data}])
            
            # Display Real AI Results
            st.subheader("📝 AI Extraction Results")
            st.markdown(response.text)
            
            st.success("Analysis Complete based on your specific criteria!")

        except Exception as e:
            st.error(f"Error reading file: {e}")

# If no file is uploaded, show the empty table as a placeholder
else:
    st.info("Please upload a file to start the automated review.")
