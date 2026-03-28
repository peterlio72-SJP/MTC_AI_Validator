import streamlit as st
import pandas as pd
import google.generativeai as genai

# Page Setup
st.set_page_config(page_title="MTC Validator", layout="wide")

# AI Logic - Fetching the secret you just saved
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("API Key not found. Check Secrets settings.")

st.title("🏗️ Engineering MTC Validator")

# Sidebar for selections
with st.sidebar:
    st.header("⚙️ Criteria")
    category = st.selectbox("Category", ["Pressure Parts", "Structural"])
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# File Uploader
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI is reading the certificate..."):
        try:
            # Using the stable model name
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Reset file pointer and read
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            
            # Check mime type
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Send to AI
            response = model.generate_content([
                {"mime_type": m_type, "data": file_bytes},
                f"Identify Heat Number, Grade, and Hardness on this MTC for {target_material}."
            ])
            
            st.subheader("📝 Extraction Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")
