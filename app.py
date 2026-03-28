"""
MatCert — Material Certificate Reviewer (Streamlit Version)
============================================================
Deploy on Streamlit Community Cloud (streamlit.io):
  1. Push this file + requirements.txt to a GitHub repo
  2. Go to share.streamlit.io → New App → connect repo
  3. In App Settings → Secrets, add:
       ANTHROPIC_API_KEY = "sk-ant-your-key-here"
  4. Deploy!
 
Local run:
  pip install -r requirements.txt
  streamlit run app.py
"""
 
import streamlit as st
import anthropic
import base64
import json
 
# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MatCert — Certificate Reviewer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@700;800&display=swap');
 
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
 
.verdict-pass  { background:#0d2e1f; border:1px solid #00c77a; border-radius:10px; padding:1rem 1.25rem; }
.verdict-fail  { background:#2e0d12; border:1px solid #ff4455; border-radius:10px; padding:1rem 1.25rem; }
.verdict-cond  { background:#2e200d; border:1px solid #ffb020; border-radius:10px; padding:1rem 1.25rem; }
 
.pill-pass    { background:#0d2e1f; color:#00c77a; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-fail    { background:#2e0d12; color:#ff4455; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-missing { background:#2e200d; color:#ffb020; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-na      { background:#1a1c22; color:#6b7280; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
 
.mono { font-family: 'IBM Plex Mono', monospace !important; }
.section-title { font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; margin-bottom:.5rem; }
.info-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:#6b7280; }
.info-value { font-family:'IBM Plex Mono',monospace; font-size:.85rem; }
</style>
""", unsafe_allow_html=True)
 
# ── Standards Database ────────────────────────────────────────────────────────
STANDARDS = {
    "ASME A106 Gr.B — Seamless Pipe": {
        "key": "ASME_A106_GR_B",
        "chemical": {
            "C":  {"max": 0.30}, "Mn": {"min": 0.29, "max": 1.06},
            "P":  {"max": 0.035}, "S":  {"max": 0.035},
            "Si": {"min": 0.10}, "Cu": {"max": 0.40},
            "Ni": {"max": 0.40}, "Cr": {"max": 0.40},
            "Mo": {"max": 0.15}, "V":  {"max": 0.08},
        },
        "mechanical": {
            "UTS (MPa)": {"min": 415}, "YS (MPa)":  {"min": 240},
            "Elongation (%)": {"min": 30},
        },
        "impact": None,
        "nace": "MR0175/ISO 15156 – HIC & SSC resistance required for sour service",
    },
    "ASME A106 Gr.C — Seamless Pipe": {
        "key": "ASME_A106_GR_C",
        "chemical": {
            "C":  {"max": 0.35}, "Mn": {"min": 0.29, "max": 1.06},
            "P":  {"max": 0.035}, "S":  {"max": 0.035}, "Si": {"min": 0.10},
        },
        "mechanical": {
            "UTS (MPa)": {"min": 485}, "YS (MPa)": {"min": 275},
            "Elongation (%)": {"min": 30},
        },
        "impact": None,
        "nace": "MR0175/ISO 15156 applicable for sour service",
    },
  "ASTM A105 — Carbon Steel Forgings": {
    "key": "ASTM_A105",
    "chemical": {
        "C":  {"max": 0.35}, "Mn": {"min": 0.60, "max": 1.05},
        "P":  {"max": 0.035}, "S": {"max": 0.040},
        "Si": {"min": 0.10, "max": 0.35},
        "Cu": {"max": 0.40}, "Ni": {"max": 0.40},
        "Cr": {"max": 0.30}, "Mo": {"max": 0.12},
        "V":  {"max": 0.08},
    },
    "mechanical": {
        "UTS (MPa)": {"min": 485},
        "YS (MPa)":  {"min": 250},
        "Elongation (%)": {"min": 22},
        "Reduction of Area (%)": {"min": 30},
    },
    "impact": None,
    "nace": "NACE MR0175 HRC ≤22 for sour service forgings",
},
  "ASTM A694 F65 — High Yield Forgings": {
    "key": "ASTM_A694_F65",
    "chemical": {
        "C":  {"max": 0.35}, "Mn": {"max": 1.60},
        "P":  {"max": 0.035}, "S": {"max": 0.040},
    },
    "mechanical": {
        "UTS (MPa)": {"min": 530},
        "YS (MPa)":  {"min": 448},
        "Elongation (%)": {"min": 18},
        "Reduction of Area (%)": {"min": 30},
    },
    "impact": {"temperature": -46, "min_avg_J": 27},
    "nace": "NACE MR0175 applicable for high-pressure sour service",
},
  "EN 10216-2 P265GH — Boiler Tube": {
    "key": "EN10216_P265GH",
    "chemical": {
        "C":  {"max": 0.20}, "Mn": {"min": 0.80, "max": 1.40},
        "P":  {"max": 0.025}, "S": {"max": 0.020},
        "Si": {"max": 0.40},
    },
    "mechanical": {
        "UTS (MPa)": {"min": 410, "max": 530},
        "YS (MPa)":  {"min": 265},
        "Elongation (%)": {"min": 23},
    },
    "impact": {"temperature": -20, "min_avg_J": 27},
    "nace": "Not typically NACE-classified; verify project spec",
},
  "API 5L Gr.B — Line Pipe": {
    "key": "API5L_GRB",
    "chemical": {
        "C":  {"max": 0.28}, "Mn": {"max": 1.20},
        "P":  {"max": 0.030}, "S": {"max": 0.030},
    },
    "mechanical": {
        "UTS (MPa)": {"min": 414, "max": 758},
        "YS (MPa)":  {"min": 241, "max": 496},
        "Elongation (%)": {"min": 21},
    },
    "impact": None,
    "nace": "NACE MR0175 for sour service; HIC per TM0284",
},
    "Q355D — Structural Plate (GB/T 1591)": {
        "key": "Q355D",
        "chemical": {
            "C":  {"max": 0.20}, "Mn": {"max": 1.70}, "Si": {"max": 0.50},
            "P":  {"max": 0.025}, "S":  {"max": 0.020},
            "Nb": {"max": 0.07}, "V":  {"max": 0.20},
            "Ti": {"max": 0.20}, "Ceq":{"max": 0.45},
        },
        "mechanical": {
            "YS (MPa)": {"min": 355}, "UTS (MPa)": {"min": 470, "max": 630},
            "Elongation (%)": {"min": 22},
        },
        "impact": {"temperature": -20, "min_avg_J": 34},
        "nace": "Not typically NACE-classified; verify project spec",
    },
    "ASTM A516 Gr.70 — Pressure Vessel Plate": {
        "key": "ASTM_A516_GR70",
        "chemical": {
            "C":  {"max": 0.28}, "Mn": {"min": 0.85, "max": 1.20},
            "P":  {"max": 0.035}, "S": {"max": 0.035},
            "Si": {"min": 0.15, "max": 0.40},
        },
        "mechanical": {
            "UTS (MPa)": {"min": 485, "max": 620}, "YS (MPa)": {"min": 260},
            "Elongation (%)": {"min": 17},
        },
        "impact": None,
        "nace": "HIC per NACE TM0284 & SSC per NACE TM0177 for sour service",
    },
    "ASTM A333 Gr.6 — Low-Temp Pipe": {
        "key": "ASTM_A333_GR6",
        "chemical": {
            "C":  {"max": 0.30}, "Mn": {"min": 0.29, "max": 1.06},
            "P":  {"max": 0.025}, "S":  {"max": 0.025},
        },
        "mechanical": {
            "UTS (MPa)": {"min": 415}, "YS (MPa)": {"min": 240},
            "Elongation (%)": {"min": 30},
        },
        "impact": {"temperature": -45, "min_avg_J": 20},
        "nace": "Low-temp application; NACE per project specification",
    },
}
 
# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert materials engineer specializing in reviewing Material Test Reports (MTR) / Mill Certificates against international standards (ASME, ASTM, EN, GB/T, API, ISO, NACE).
 
When reviewing a certificate:
1. Extract ALL chemical composition values found
2. Extract ALL mechanical test results (UTS, YS, elongation, hardness, reduction of area)
3. Extract impact test results if present (temperature, individual and average energy)
4. Compare each value against the provided standard limits
5. Flag FAIL for any out-of-spec value, MISSING for required but absent values, PASS for conforming values
6. Note NACE compliance (hardness HRC ≤22, HIC, SSC test results)
7. Give an overall PASS / FAIL / CONDITIONAL verdict
 
Respond ONLY in valid JSON matching this exact schema (no markdown fences, no preamble):
{
  "document_info": {
    "heat_number": "string or null",
    "lot_number": "string or null",
    "material_grade": "string or null",
    "manufacturer": "string or null",
    "po_number": "string or null",
    "test_date": "string or null"
  },
  "chemical_composition": {
    "ELEMENT": {"found": number_or_null, "min": number_or_null, "max": number_or_null, "unit": "%", "status": "PASS|FAIL|MISSING"}
  },
  "mechanical_properties": {
    "PROPERTY": {"found": number_or_null, "min": number_or_null, "max": number_or_null, "unit": "string", "status": "PASS|FAIL|MISSING"}
  },
  "impact_tests": {
    "temperature": number_or_null,
    "unit": "°C",
    "specimens": [{"id": "string", "energy": number, "unit": "J"}],
    "average": number_or_null,
    "required_avg": number_or_null,
    "status": "PASS|FAIL|MISSING|N/A"
  },
  "nace_compliance": {
    "applicable": true_or_false,
    "standard": "string",
    "hardness_hrc": number_or_null,
    "hardness_limit": 22,
    "hic_tested": true_or_false,
    "ssc_tested": true_or_false,
    "status": "PASS|FAIL|NOT_TESTED|N/A",
    "notes": "string"
  },
  "overall_verdict": "PASS|FAIL|CONDITIONAL",
  "failed_items": ["string"],
  "missing_items": ["string"],
  "warnings": ["string"],
  "summary": "string"
}"""
 
# ── Helpers ───────────────────────────────────────────────────────────────────
def encode_file(file_bytes: bytes) -> str:
    return base64.standard_b64encode(file_bytes).decode("utf-8")
 
def get_client():
    try:
        key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        key = None
    if not key:
        st.error("❌ **ANTHROPIC_API_KEY not found.** Add it in Streamlit → Settings → Secrets, or create a `.streamlit/secrets.toml` file locally.")
        st.stop()
    return anthropic.Anthropic(api_key=key)
 
def status_badge(status: str) -> str:
    mapping = {
        "PASS":      '<span class="pill-pass">✓ PASS</span>',
        "FAIL":      '<span class="pill-fail">✕ FAIL</span>',
        "MISSING":   '<span class="pill-missing">? MISSING</span>',
        "N/A":       '<span class="pill-na">– N/A</span>',
        "NOT_TESTED":'<span class="pill-na">– NOT TESTED</span>',
    }
    return mapping.get(status, f'<span class="pill-na">{status}</span>')
 
def call_claude(file_bytes: bytes, media_type: str, standard_name: str,
                standard: dict, nace_required: bool, notes: str) -> dict:
    client = get_client()
    b64 = encode_file(file_bytes)
    doc_type = "document" if media_type == "application/pdf" else "image"
 
    context = f"""
STANDARD: {standard_name} ({standard['key']})
CHEMICAL COMPOSITION LIMITS: {json.dumps(standard['chemical'], indent=2)}
MECHANICAL PROPERTY LIMITS:  {json.dumps(standard['mechanical'], indent=2)}
IMPACT TEST REQUIREMENTS:    {json.dumps(standard.get('impact') or {'note': 'Not required for this standard'}, indent=2)}
NACE NOTE:                   {standard['nace']}
PROJECT NACE REQUIRED:       {nace_required}
ADDITIONAL REVIEWER NOTES:   {notes or 'None'}
 
Review the attached certificate against ALL requirements above and respond in the required JSON schema.
"""
    if doc_type == "document":
        content = [
            {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": context},
        ]
    else:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": context},
        ]
 
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
 
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
 
# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 MatCert")
    st.markdown("*AI-powered material certificate reviewer*")
    st.divider()
 
    uploaded_file = st.file_uploader(
        "Upload Certificate",
        type=["pdf", "jpg", "jpeg", "png", "webp"],
        help="Upload a PDF or image of the material test report / mill certificate",
    )
 
    standard_name = st.selectbox("Material Standard", list(STANDARDS.keys()))
    standard = STANDARDS[standard_name]
 
    nace_required = st.toggle("NACE / Sour Service Required", value=False,
                              help="Enable if project specification requires NACE MR0175 or sour service compliance")
 
    notes = st.text_area("Additional Notes (optional)",
                         placeholder="e.g. HIC test required, wall thickness 25mm, heat treatment condition…",
                         height=90)
 
    st.divider()
    review_btn = st.button("🔍 Review Certificate", type="primary",
                           disabled=(uploaded_file is None), use_container_width=True)
 
    st.divider()
    st.markdown("**Supported Standards**")
    st.markdown("""
- ASME A106 Gr.B / Gr.C
- ASTM A516 Gr.70
- ASTM A333 Gr.6
- Q355D (GB/T 1591)
- NACE MR0175 / TM0284 / TM0177
""")
 
# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("# Material Certificate Reviewer")
st.markdown("Upload a mill certificate, select the applicable standard, and let AI verify compliance automatically.")
 
if not uploaded_file and not review_btn:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Step 1** — Upload a PDF or image of your material certificate using the sidebar.")
    with col2:
        st.info("**Step 2** — Select the applicable material standard (ASME, ASTM, Q355D, etc.).")
    with col3:
        st.info("**Step 3** — Click **Review Certificate** to get an instant AI compliance verdict.")
    st.stop()
 
# ── Run review ────────────────────────────────────────────────────────────────
if review_btn and uploaded_file:
    file_bytes = uploaded_file.read()
    fname = uploaded_file.name.lower()
 
    if fname.endswith(".pdf"):
        media_type = "application/pdf"
    elif fname.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif fname.endswith(".png"):
        media_type = "image/png"
    elif fname.endswith(".webp"):
        media_type = "image/webp"
    else:
        st.error("Unsupported file type. Please upload PDF, JPG, PNG, or WEBP.")
        st.stop()
 
    with st.spinner("Analyzing certificate… this may take 15–30 seconds."):
        try:
            result = call_claude(file_bytes, media_type, standard_name,
                                 standard, nace_required, notes)
            st.session_state["result"] = result
            st.session_state["filename"] = uploaded_file.name
            st.session_state["standard_name"] = standard_name
        except json.JSONDecodeError as e:
            st.error(f"Could not parse AI response as JSON: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Error calling Anthropic API: {e}")
            st.stop()
 
# ── Display results ───────────────────────────────────────────────────────────
if "result" in st.session_state:
    r = st.session_state["result"]
    fname = st.session_state.get("filename", "")
    sname = st.session_state.get("standard_name", "")
 
    verdict = r.get("overall_verdict", "CONDITIONAL")
    verdict_color = {"PASS": "verdict-pass", "FAIL": "verdict-fail"}.get(verdict, "verdict-cond")
    verdict_icon  = {"PASS": "✅", "FAIL": "❌"}.get(verdict, "⚠️")
    verdict_text  = {"PASS": "Certificate APPROVED", "FAIL": "Certificate REJECTED"}.get(verdict, "Conditional — Review Required")
 
    st.markdown(f"""
    <div class="{verdict_color}">
      <span style="font-size:1.5rem">{verdict_icon}</span>
      <strong style="font-family:'Syne',sans-serif;font-size:1.2rem;margin-left:.5rem">{verdict_text}</strong>
      <span style="font-size:.8rem;color:#9ca3af;margin-left:.75rem">{sname} · {fname}</span>
    </div>
    """, unsafe_allow_html=True)
 
    st.markdown("")
 
    # ── Document info ──
    di = r.get("document_info", {})
    if any(di.values()):
        cols = st.columns(6)
        fields = [("Heat No.", "heat_number"), ("Lot No.", "lot_number"),
                  ("Grade", "material_grade"), ("Manufacturer", "manufacturer"),
                  ("PO No.", "po_number"), ("Test Date", "test_date")]
        for col, (label, key) in zip(cols, fields):
            with col:
                st.markdown(f'<div class="info-label">{label}</div><div class="info-value">{di.get(key) or "—"}</div>', unsafe_allow_html=True)
        st.divider()
 
    # ── Tabs ──
    failed_count  = len(r.get("failed_items", []))
    missing_count = len(r.get("missing_items", []))
    issues_label  = f"Issues ({failed_count + missing_count})" if failed_count + missing_count else "Issues"
 
    tab_chem, tab_mech, tab_impact, tab_nace, tab_issues = st.tabs(
        ["🧪 Chemistry", "⚙️ Mechanical", "❄️ Impact Test", "🛡️ NACE", issues_label]
    )
 
    # ── Chemistry tab ──
    with tab_chem:
        chem = r.get("chemical_composition", {})
        if chem:
            rows = []
            for el, v in chem.items():
                rows.append({
                    "Element": el,
                    "Found": v.get("found") if v.get("found") is not None else "—",
                    "Min": v.get("min") if v.get("min") is not None else "—",
                    "Max": v.get("max") if v.get("max") is not None else "—",
                    "Unit": v.get("unit", "%"),
                    "Status": v.get("status", "—"),
                })
            # Display with colored status
            header_cols = st.columns([1.2, 1.2, 1.2, 1.2, 0.8, 1.5])
            for col, h in zip(header_cols, ["Element", "Found", "Min", "Max", "Unit", "Status"]):
                col.markdown(f"**{h}**")
            for row in rows:
                cols = st.columns([1.2, 1.2, 1.2, 1.2, 0.8, 1.5])
                cols[0].markdown(f"`{row['Element']}`")
                cols[1].write(row["Found"])
                cols[2].write(row["Min"])
                cols[3].write(row["Max"])
                cols[4].write(row["Unit"])
                cols[5].markdown(status_badge(row["Status"]), unsafe_allow_html=True)
        else:
            st.info("No chemical composition data found in the certificate.")
 
    # ── Mechanical tab ──
    with tab_mech:
        mech = r.get("mechanical_properties", {})
        if mech:
            header_cols = st.columns([2, 1.2, 1.2, 1.2, 1.2, 1.5])
            for col, h in zip(header_cols, ["Property", "Found", "Min", "Max", "Unit", "Status"]):
                col.markdown(f"**{h}**")
            for prop, v in mech.items():
                cols = st.columns([2, 1.2, 1.2, 1.2, 1.2, 1.5])
                cols[0].write(prop)
                cols[1].write(v.get("found") if v.get("found") is not None else "—")
                cols[2].write(v.get("min") if v.get("min") is not None else "—")
                cols[3].write(v.get("max") if v.get("max") is not None else "—")
                cols[4].write(v.get("unit", ""))
                cols[5].markdown(status_badge(v.get("status", "—")), unsafe_allow_html=True)
        else:
            st.info("No mechanical property data found.")
 
    # ── Impact tab ──
    with tab_impact:
        imp = r.get("impact_tests", {})
        if imp and imp.get("status") != "N/A":
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Test Temperature", f"{imp.get('temperature', '—')} {imp.get('unit','°C')}")
            col2.metric("Average Energy", f"{imp.get('average', '—')} J")
            col3.metric("Required Average", f"{imp.get('required_avg', '—')} J")
            col4.markdown("**Status**")
            col4.markdown(status_badge(imp.get("status", "—")), unsafe_allow_html=True)
 
            specimens = imp.get("specimens", [])
            if specimens:
                st.markdown("**Individual Specimens**")
                spec_cols = st.columns(len(specimens))
                for col, s in zip(spec_cols, specimens):
                    col.metric(s.get("id", "Specimen"), f"{s.get('energy','—')} {s.get('unit','J')}")
        else:
            st.info("No impact test data found / not required for this standard.")
 
    # ── NACE tab ──
    with tab_nace:
        nace = r.get("nace_compliance", {})
        if nace:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**NACE Compliance Details**")
                st.markdown(f"**Standard:** {nace.get('standard','—')}")
                st.markdown(f"**Applicable:** {'Yes' if nace.get('applicable') else 'No'}")
                hrc = nace.get("hardness_hrc")
                lim = nace.get("hardness_limit", 22)
                st.markdown(f"**Hardness HRC:** {hrc if hrc is not None else '—'} / max {lim}")
                st.markdown(f"**HIC Tested:** {'✅ Yes' if nace.get('hic_tested') else '❌ No'}")
                st.markdown(f"**SSC Tested:** {'✅ Yes' if nace.get('ssc_tested') else '❌ No'}")
                st.markdown("**Overall Status:**")
                st.markdown(status_badge(nace.get("status", "—")), unsafe_allow_html=True)
            with col2:
                st.markdown("**Notes**")
                st.info(nace.get("notes") or standard["nace"])
        else:
            st.info("No NACE compliance data available.")
 
    # ── Issues tab ──
    with tab_issues:
        failed_items  = r.get("failed_items", [])
        missing_items = r.get("missing_items", [])
        warnings      = r.get("warnings", [])
 
        if not failed_items and not missing_items and not warnings:
            st.success("✅ No issues found — all values are within specification.")
        else:
            if failed_items:
                st.markdown("#### ❌ Failed Items")
                for item in failed_items:
                    st.error(item)
            if missing_items:
                st.markdown("#### ⚠️ Missing Items")
                for item in missing_items:
                    st.warning(item)
            if warnings:
                st.markdown("#### ℹ️ Warnings")
                for w in warnings:
                    st.info(w)
 
    # ── Summary ──
    if r.get("summary"):
        st.divider()
        st.markdown("**Review Summary**")
        st.markdown(r["summary"])
 
    # ── Download JSON ──
    st.divider()
    st.download_button(
        "⬇️ Download Full Review (JSON)",
        data=json.dumps(r, indent=2),
        file_name=f"review_{fname.replace(' ','_')}.json",
        mime="application/json",
    )
