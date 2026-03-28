import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

# 1. Page Config
st.set_page_config(page_title="MTC AI Validator", layout="wide")

# 2. Secure AI Setup
if "GOOGLE_API_KEY" in st.secrets:
    # FORCING API VERSION V1 TO AVOID 404 BETA ERROR
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')
else:
    st.error("Missing API Key in Secrets!")

st.title("🏗️ Engineering MTC Validator")

# 3. Sidebar Selection
with st.sidebar:
    st.header("⚙️ Selection")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 4. Main Upload Logic
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI Reviewing..."):
        try:
            # USING THE FULL MODEL PATH
            model = genai.GenerativeModel('models/gemini-1.5-flash')
            
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # THE REQUEST
            response = model.generate_content(
                contents=[
                    {"mime_type": m_type, "data": file_data},
                    {"text": f"Extract Heat Number, Grade, and Hardness for {target_material}."}
                ]
            )
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            st.info("Try refreshing the page or checking your API key status.")
