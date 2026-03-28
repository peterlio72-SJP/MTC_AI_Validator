import streamlit as st
import pandas as pd
import google.generativeai as genai

# 1. Setup Page
st.set_page_config(page_title="MTC AI Validator", layout="wide")

# 2. AI Configuration
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("Missing API Key in Secrets!")

st.title("🏗️ Engineering MTC Validator")

# 3. Sidebar Selection
with st.sidebar:
    st.header("⚙️ Selection")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 4. Main Upload Logic
uploaded_file = st.file_uploader("Upload MTC", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI Reviewing..."):
        try:
            # We use the most robust model string
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Reset and Read File
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            
            # Identify Mime Type
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Simplified Content List
            contents = [
                {"mime_type": m_type, "data": file_data},
                f"Identify Heat Number, Grade, and Hardness for {target_material}."
            ]
            
            # Execution
            response = model.generate_content(contents)
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
