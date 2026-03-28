import streamlit as st
import google.generativeai as genai

# 1. Setup
st.set_page_config(page_title="MTC AI Validator", layout="wide")
api_key = st.secrets.get("GOOGLE_API_KEY")

# 2. THE VERSION LOCK: Forcing V1 Stable
if api_key:
    genai.configure(api_key=api_key, transport='rest')
else:
    st.error("Missing API Key in Secrets!")

st.title("🏗️ Engineering MTC Validator")

# 3. Sidebar
with st.sidebar:
    st.header("⚙️ Criteria")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 4. Main Upload
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI Reviewing (Stable V1 Mode)..."):
        try:
            # Using the absolute most compatible model name
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # The Content Request
            response = model.generate_content([
                {"mime_type": m_type, "data": file_data},
                f"You are a Quality Control Engineer. Identify Heat Number, Grade, and Hardness for {target_material}."
            ])
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            st.info("If you see a 404, we may need to regenerate your API Key in Google AI Studio one more time.")
