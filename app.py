import streamlit as st
import google.generativeai as genai
from google.generativeai import Client

# 1. Page Configuration
st.set_page_config(page_title="MTC AI Validator", layout="wide")

# 2. Force the Stable V1 API
if "GOOGLE_API_KEY" in st.secrets:
    # This specific line forces the app to skip the broken 'v1beta' path
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"], http_options={'api_version': 'v1'})
else:
    st.error("Missing API Key in Secrets!")

st.title("🏗️ Engineering MTC Validator")

# 3. Sidebar
with st.sidebar:
    st.header("⚙️ Selection")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 4. Main Upload Logic
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI Reviewing..."):
        try:
            # We call the model directly through the client to ensure v1 usage
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Direct generation call
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[
                    {"mime_type": m_type, "data": file_bytes},
                    f"Extract Heat Number, Grade, and Hardness for {target_material}."
                ]
            )
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            # If it still fails, this will show us the new error
            st.error(f"Analysis failed: {str(e)}")
