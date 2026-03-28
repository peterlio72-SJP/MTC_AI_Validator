import streamlit as st
import pandas as pd
import requests
import base64

# 1. Setup
st.set_page_config(page_title="MTC AI Validator", layout="wide")
api_key = st.secrets.get("GOOGLE_API_KEY")

st.title("🏗️ Engineering MTC Validator")

# 2. Sidebar
with st.sidebar:
    st.header("⚙️ Criteria")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 3. File Upload
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file and api_key:
    with st.spinner("🤖 AI Reviewing via Direct Stable Connection..."):
        try:
            # Convert file to Base64
            uploaded_file.seek(0)
            file_data = base64.b64encode(uploaded_file.read()).decode('utf-8')
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # --- THE URL: Stable V1 Path ---
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            # --- THE PAYLOAD: Using camelCase (inlineData) for the stable API ---
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Extract Heat Number, Grade, and Hardness for {target_material} from this MTC."},
                        {
                            "inlineData": {
                                "mimeType": m_type,
                                "data": file_data
                            }
                        }
                    ]
                }]
            }
            
            # Send the request
            response = requests.post(url, json=payload)
            res_json = response.json()
            
            if "candidates" in res_json:
                output_text = res_json['candidates'][0]['content']['parts'][0]['text']
                st.subheader("📝 Extraction Results")
                st.markdown(output_text)
            else:
                st.error(f"API Error Detail: {res_json}")
                
        except Exception as e:
            st.error(f"Technical Failure: {str(e)}")

elif not api_key:
    st.warning("API Key missing from Secrets.")
