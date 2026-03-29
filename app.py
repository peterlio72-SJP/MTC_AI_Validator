import streamlit as st
import anthropic
import base64
import json

st.title("🔬 MatCert — Certificate Reviewer")

try:
    key = st.secrets["ANTHROPIC_API_KEY"]
except:
    st.error("Add ANTHROPIC_API_KEY to Streamlit Secrets")
    st.stop()

uploaded = st.file_uploader("Upload Mill Certificate", type=["pdf","jpg","jpeg","png"])

if uploaded and st.button("Review Certificate", type="primary"):
    with st.spinner("Reviewing... please wait 20-30 seconds"):
        file_bytes = uploaded.read()
        b64_data = base64.standard_b64encode(file_bytes).decode()
        name = uploaded.name.lower()
        if name.endswith(".pdf"):
            block = {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":b64_data}}
        else:
            block = {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b64_data}}

        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3000,
            system="You are a materials engineer. Review mill certificates against standards.",
            messages=[{"role":"user","content":[block,{"type":"text","text":"""Review this mill certificate. Respond in JSON only:
{
  "standard": "full standard name",
  "grade": "grade",
  "heat_number": "value or null",
  "manufacturer": "value or null",
  "verdict": "PASS or FAIL or CONDITIONAL",
  "chemical": {"ELEMENT": {"found": null, "min": null, "max": null, "status": "PASS or FAIL or MISSING"}},
  "mechanical": {"PROPERTY": {"found": null, "min": null, "max": null, "unit": "", "status": "PASS or FAIL or MISSING"}},
  "failed": ["list"],
  "summary": "brief summary"
}"""}]}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        result = json.loads(raw.strip())

    verdict = result.get("verdict","?")
    if verdict == "PASS": st.success("✅ PASS — Certificate Approved")
    elif verdict == "FAIL": st.error("❌ FAIL — Certificate Rejected")
    else: st.warning("⚠️ CONDITIONAL — Review Required")

    col1, col2 = st.columns(2)
    col1.metric("Standard", result.get("standard","—"))
    col2.metric("Heat No.", result.get("heat_number","—"))

    st.subheader("🧪 Chemistry")
    for el, v in result.get("chemical",{}).items():
        c = st.columns([1,1,1,1,1])
        c[0].write(el); c[1].write(str(v.get("found","—")))
        c[2].write(str(v.get("min","—"))); c[3].write(str(v.get("max","—")))
        s = v.get("status","—")
        if s=="PASS": c[4].success(s)
        elif s=="FAIL": c[4].error(s)
        else: c[4].warning(s)

    st.subheader("⚙️ Mechanical")
    for prop, v in result.get("mechanical",{}).items():
        c = st.columns([2,1,1,1,1])
        c[0].write(prop); c[1].write(str(v.get("found","—")))
        c[2].write(str(v.get("min","—"))); c[3].write(str(v.get("max","—")))
        s = v.get("status","—")
        if s=="PASS": c[4].success(s)
        elif s=="FAIL": c[4].error(s)
        else: c[4].warning(s)

    for f in result.get("failed",[]): st.error(f"❌ {f}")
    st.info(result.get("summary",""))
