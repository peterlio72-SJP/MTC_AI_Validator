import streamlit as st
import google.generativeai as genai

# 1. Page Config
st.set_page_config(page_title="MTC AI Validator", layout="wide")

# 2. Stable AI Setup (Restricting to stable transport)
if "GOOGLE_API_KEY" in st.secrets:
    # 'rest' transport is the most reliable way to avoid the v1beta 404 error
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')
else:
    st.error("Missing API Key in Secrets!")

st.title("🏗️ Engineering MTC Validator")

# 3. Selection
with st.sidebar:
    st.header("⚙️ Criteria")
    target_material = st.selectbox("Grade", ["Q355D", "A106 Gr. B", "A516 Gr. 65"])

# 4. Main Upload
uploaded_file = st.file_uploader("Upload MTC (PDF/Image)", type=['pdf', 'jpg', 'png'])

if uploaded_file:
    with st.spinner("🤖 AI Reviewing..."):
        try:
            # We use the pro model if flash is having routing issues
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Simple content delivery
            response = model.generate_content([
                {"mime_type": m_type, "data": file_bytes},
                f"Extract Heat Number, Grade, and Hardness for {target_material} from this MTC."
            ])
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
