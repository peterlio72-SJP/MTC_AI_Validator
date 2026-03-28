import streamlit as st
import google.generativeai as genai

# 1. Page Configuration
st.set_page_config(page_title="MTC AI Validator", layout="wide")

# 2. Stable AI Setup
if "GOOGLE_API_KEY" in st.secrets:
    # We use 'rest' transport to avoid the broken gRPC beta paths
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')
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
            # Use the most stable model naming convention
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            
            m_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "image/jpeg"
            
            # Simple, direct content list
            response = model.generate_content([
                {"mime_type": m_type, "data": file_bytes},
                f"Extract Heat Number, Grade, and Hardness for {target_material}."
            ])
            
            st.subheader("📝 Results")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
