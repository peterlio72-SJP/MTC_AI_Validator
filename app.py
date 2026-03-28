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
    with st.spinner("🤖 AI is reviewing compliance..."):
        try:
            # Using the ABSOLUTE path to the model to avoid 404
            model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
            
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            
            # Determine file type
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Constructing the message in the new format
            contents = [
                {
                    "role": "user",
                    "parts": [
                        {"mime_type": m_type, "data": file_bytes},
                        {"text": f"Identify Heat Number, Grade, and Hardness for {target_material}."}
                    ]
                }
            ]
            
            # Call the AI using the robust method
            response = model.generate_content(contents)
            
            st.subheader("📝 Extraction Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")
