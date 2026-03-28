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
            # TRYING THE PRO MODEL (Often more stable with PDFs)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            # Important: Ensure the file is read correctly
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            
            # Prepare the content list
            content_to_send = [
                {"mime_type": "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg", 
                 "data": file_data},
                f"Identify the Heat Number and Material Grade on this MTC. Target: {target_material}."
            ]
            
            # Explicitly telling it to generate content
            response = model.generate_content(content_to_send)
            
            st.subheader("📝 AI Extraction Results")
            st.markdown(response.text)
            
        except Exception as e:
            # This will show us if the error changed
            st.error(f"Current Technical Error: {e}")

# If no file is uploaded, show the empty table as a placeholder
else:
    st.info("Please upload a file to start the automated review.")
