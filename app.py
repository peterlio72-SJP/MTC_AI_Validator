import streamlit as st
import anthropic
import base64
import json

# ── Page setup ────────────────────────────────────
st.set_page_config(
    page_title="MatCert — MTC Reviewer",
    page_icon="🔬",
    layout="centered"
)

st.markdown("""
<style>
.pass  { color: #00c77a; font-weight: bold; font-size: 1.3rem; }
.fail  { color: #ff4455; font-weight: bold; font-size: 1.3rem; }
.cond  { color: #ffb020; font-weight: bold; font-size: 1.3rem; }
.label { color: #888; font-size: 0.75rem; text-transform: uppercase; }
.value { font-family: monospace; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────
st.markdown("# 🔬 MatCert")
st.markdown("**Material Test Certificate Reviewer** — ASME · ASTM · API · EN · GB/T")
st.divider()

# ── API Key ────────────────────────────────────────
try:
    key = st.secrets["ANTHROPIC_API_KEY"]
except:
    st.error("❌ ANTHROPIC_API_KEY not found in Streamlit Secrets")
    st.stop()

# ── Upload ─────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload Mill Certificate",
    type=["pdf", "jpg", "jpeg", "png"],
    help="PDF or image of the material test certificate"
)

if uploaded:
    st.caption(f"📄 {uploaded.name} — {round(uploaded.size/1024, 1)} KB")

    if st.button("🔍 Review Certificate", type="primary", use_container_width=True):

        with st.spinner("AI is reading the certificate and checking against standards... (20–40 sec)"):

            # Read and encode file
            file_bytes = uploaded.read()
            b64_data   = base64.standard_b64encode(file_bytes).decode()
            fname      = uploaded.name.lower()

            # Build content block
            if fname.endswith(".pdf"):
                block = {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64_data
                    }
                }
            else:
                mt = "image/jpeg" if fname.endswith((".jpg",".jpeg")) else "image/png"
                block = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mt,
                        "data": b64_data
                    }
                }

            # Call Claude
            client = anthropic.Anthropic(api_key=key, timeout=60.0)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                system="""You are a senior materials engineer specializing in
mill certificate review against ASME, ASTM, API 5L, EN, GB/T, and NACE standards.
Always identify the correct standard from the certificate itself.
Apply exact limits from your knowledge of that standard.
Be precise and thorough.""",
                messages=[{
                    "role": "user",
                    "content": [
                        block,
                        {
                            "type": "text",
                            "text": """Review this mill certificate carefully.
Identify the standard automatically from the certificate.
Compare every value against the correct standard limits.

Respond ONLY in valid JSON, no markdown:
{
  "standard": "e.g. ASTM A106 Grade B",
  "specification": "e.g. ASTM A106",
  "grade": "e.g. Grade B",
  "heat_number": "value or null",
  "lot_number": "value or null",
  "manufacturer": "value or null",
  "test_date": "value or null",
  "product_form": "e.g. Seamless Pipe",
  "size": "e.g. 4 inch SCH 40 or null",
  "verdict": "PASS or FAIL or CONDITIONAL",
  "chemical": {
    "C":  {"found": 0.0, "min": null, "max": 0.0, "status": "PASS"},
    "Mn": {"found": 0.0, "min": 0.0,  "max": 0.0, "status": "PASS"}
  },
  "mechanical": {
    "UTS (MPa)":        {"found": 0, "min": 0, "max": null, "status": "PASS"},
    "YS (MPa)":         {"found": 0, "min": 0, "max": null, "status": "PASS"},
    "Elongation (%)":   {"found": 0, "min": 0, "max": null, "status": "PASS"}
  },
  "impact": {
    "required": false,
    "temperature": null,
    "average_J": null,
    "required_J": null,
    "status": "NA"
  },
  "failed_items":  [],
  "missing_items": [],
  "warnings":      [],
  "summary": "One paragraph summary of the review"
}"""
                        }
                    ]
                }]
            )

            # Parse response
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())

        # ── Store in session ──────────────────────────
        st.session_state["result"]   = result
        st.session_state["filename"] = uploaded.name

# ── Show Results ───────────────────────────────────
if "result" in st.session_state:
    r       = st.session_state["result"]
    verdict = r.get("verdict", "CONDITIONAL")

    st.divider()

    # Verdict
    if verdict == "PASS":
        st.markdown('<p class="pass">✅ PASS — Certificate Approved</p>', unsafe_allow_html=True)
    elif verdict == "FAIL":
        st.markdown('<p class="fail">❌ FAIL — Certificate Rejected</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="cond">⚠️ CONDITIONAL — Review Required</p>', unsafe_allow_html=True)

    # Document info
    cols = st.columns(4)
    fields = [
        ("Standard",     r.get("standard", "—")),
        ("Heat No.",     r.get("heat_number", "—")),
        ("Manufacturer", r.get("manufacturer", "—")),
        ("Test Date",    r.get("test_date", "—")),
    ]
    for col, (label, value) in zip(cols, fields):
        with col:
            st.markdown(f'<div class="label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{value or "—"}</div>', unsafe_allow_html=True)

    st.markdown("")
    cols2 = st.columns(4)
    fields2 = [
        ("Grade",        r.get("grade", "—")),
        ("Product Form", r.get("product_form", "—")),
        ("Size",         r.get("size", "—")),
        ("Lot No.",      r.get("lot_number", "—")),
    ]
    for col, (label, value) in zip(cols2, fields2):
        with col:
            st.markdown(f'<div class="label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{value or "—"}</div>', unsafe_allow_html=True)

    st.divider()

    # Chemistry + Mechanical side by side
    col_chem, col_mech = st.columns(2)

    with col_chem:
        st.markdown("#### 🧪 Chemical Composition (%)")
        chem = r.get("chemical", {})
        if chem:
            hc = st.columns([1, 1, 1, 1, 1.5])
            for h, label in zip(hc, ["El.", "Found", "Min", "Max", "Status"]):
                h.markdown(f"**{label}**")
            for el, v in chem.items():
                c = st.columns([1, 1, 1, 1, 1.5])
                c[0].write(f"`{el}`")
                c[1].write(str(v.get("found", "—")))
                c[2].write(str(v.get("min", "—") if v.get("min") is not None else "—"))
                c[3].write(str(v.get("max", "—") if v.get("max") is not None else "—"))
                s = v.get("status", "—")
                if s == "PASS":    c[4].success(s)
                elif s == "FAIL":  c[4].error(s)
                else:              c[4].warning(s)
        else:
            st.info("No chemical data found")

    with col_mech:
        st.markdown("#### ⚙️ Mechanical Properties")
        mech = r.get("mechanical", {})
        if mech:
            hm = st.columns([2, 1, 1, 1, 1.5])
            for h, label in zip(hm, ["Property", "Found", "Min", "Max", "Status"]):
                h.markdown(f"**{label}**")
            for prop, v in mech.items():
                c = st.columns([2, 1, 1, 1, 1.5])
                c[0].write(prop)
                c[1].write(str(v.get("found", "—")))
                c[2].write(str(v.get("min", "—") if v.get("min") is not None else "—"))
                c[3].write(str(v.get("max", "—") if v.get("max") is not None else "—"))
                s = v.get("status", "—")
                if s == "PASS":    c[4].success(s)
                elif s == "FAIL":  c[4].error(s)
                else:              c[4].warning(s)
        else:
            st.info("No mechanical data found")

    # Impact tests
    imp = r.get("impact", {})
    if imp.get("required") and imp.get("status") != "NA":
        st.divider()
        st.markdown("#### ❄️ Impact Tests")
        ci = st.columns(4)
        ci[0].metric("Temperature", f"{imp.get('temperature','—')} °C")
        ci[1].metric("Average Energy", f"{imp.get('average_J','—')} J")
        ci[2].metric("Required", f"{imp.get('required_J','—')} J")
        s = imp.get("status","—")
        ci[3].markdown("**Status**")
        if s == "PASS":   ci[3].success(s)
        elif s == "FAIL": ci[3].error(s)
        else:             ci[3].warning(s)

    # Issues
    failed  = r.get("failed_items", [])
    missing = r.get("missing_items", [])
    warnings= r.get("warnings", [])

    if failed or missing or warnings:
        st.divider()
        st.markdown("#### 🚨 Issues Found")
        for item in failed:   st.error(f"❌ {item}")
        for item in missing:  st.warning(f"⚠️ {item}")
        for item in warnings: st.info(f"ℹ️ {item}")
    else:
        st.divider()
        st.success("✅ No issues found — all values within specification")

    # Summary
    st.divider()
    st.markdown("#### 📝 Review Summary")
    st.info(r.get("summary", ""))

    st.caption(f"File: {st.session_state.get('filename','')} · Reviewed by MatCert AI")
