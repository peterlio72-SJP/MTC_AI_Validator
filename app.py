import streamlit as st
import anthropic
import base64
import json

st.title("MatCert")

key = st.secrets["ANTHROPIC_API_KEY"]
uploaded = st.file_uploader("Upload Certificate PDF")

if uploaded:
    if st.button("Review"):
        data = uploaded.read()
        b64 = base64.b64encode(data).decode()
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role":"user","content":[
                {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":b64}},
                {"type":"text","text":"Review this mill certificate. List: standard, verdict PASS/FAIL, chemical values, mechanical values, any failures."}
            ]}]
        )
        st.write(r.content[0].text)
