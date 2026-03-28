import streamlit as st
import pandas as pd
import requests
import base64

# --- Page Config ---
st.set_page_config(page_title="MTC AI Validator", layout="wide")
api_key = st.secrets.get("GOOGLE_API_KEY")

st.title("🏗️ Engineering MTC Validator")

with st.sidebar:
    st.header("⚙️ Selection")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file and api_key:
    with st.spinner("🤖 AI Reviewing Certificate..."):
        try:
            # 1. Prepare File
            uploaded_file.seek(0)
            file_data = base64.b64encode(uploaded_file.read()).decode('utf-8')
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # 2. Use the stable V1 URL with the new key
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Extract Heat Number, Grade, and Hardness for {target_material}."},
                        {"inlineData": {"mimeType": m_type, "data": file_data}}
                    ]
                }]
            }
            
            # 3. Direct Connection
            response = requests.post(url, json=payload)
            res_json = response.json()
            
            if "candidates" in res_json:
                st.subheader("📝 Extraction Results")
                st.markdown(res_json['candidates'][0]['content']['parts'][0]['text'])
            else:
                st.error(f"API Error: {res_json}")
                
        except Exception as e:
            st.error(f"Technical Failure: {str(e)}")
