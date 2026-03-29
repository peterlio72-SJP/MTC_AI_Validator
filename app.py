import streamlit as st
import anthropic
import httpx
import base64
import json

st.title("MatCert")

key = st.secrets["ANTHROPIC_API_KEY"]
uploaded = st.file_uploader("Upload Certificate PDF")

if uploaded:
    if st.button("Review"):
        data = uploaded.read()
        b64 = base64.b64encode(data).decode()
       client = anthropic.Anthropic(
    api_key=st.secrets["ANTHROPIC_API_KEY"],
    http_client=httpx.Client(
        headers={"User-Agent": "MatCert/1.0"},
        timeout=60.0
    )
)
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role":"user","content":[
                {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":b64}},
                {"type":"text","text":"Review this mill certificate. List: standard, verdict PASS/FAIL, chemical values, mechanical values, any failures."}
            ]}]
        )
        st.write(r.content[0].text)
