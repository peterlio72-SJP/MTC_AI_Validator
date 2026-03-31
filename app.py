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
.nace-on  { background:#0d2e1f; border:1px solid #00c77a; border-radius:8px;
            padding:8px 14px; font-size:0.85rem; color:#00c77a; margin-bottom:8px; }
.nace-off { background:#1a1c22; border:1px solid #444; border-radius:8px;
            padding:8px 14px; font-size:0.85rem; color:#888; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None
if "filename" not in st.session_state:
    st.session_state.filename = ""
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ── Header ─────────────────────────────────────────
col_title, col_clear = st.columns([4, 1])
with col_title:
    st.markdown("# 🔬 MatCert")
    st.markdown("**Material Test Certificate Reviewer** — ASME · ASTM · API · EN · GB/T")
with col_clear:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Clear", use_container_width=True, help="Clear and start new review"):
        st.session_state.result = None
        st.session_state.filename = ""
        st.session_state.uploader_key += 1
        st.rerun()

st.divider()

# ── API Key ────────────────────────────────────────
try:
    key = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    st.error("❌ ANTHROPIC_API_KEY not found in Streamlit Secrets")
    st.stop()

# ── Upload + Options ───────────────────────────────
uploaded = st.file_uploader(
    "Upload Mill Certificate (PDF or Image — max 5MB)",
    type=["pdf", "jpg", "jpeg", "png"],
    key=f"uploader_{st.session_state.uploader_key}",
    help="Supports PDF, JPG, PNG up to 5MB"
)

# ── NACE Toggle ────────────────────────────────────
st.markdown("#### 🛡️ Sour Service / NACE Requirement")
nace_required = st.toggle(
    "NACE MR0175 / ISO 15156 Required",
    value=False,
    help="Turn ON if this material is for sour service (H2S environment). The AI will check hardness HRC ≤22, HIC test, SSC test compliance."
)

if nace_required:
    st.markdown("""
    <div class="nace-on">
    ✅ <strong>NACE ON</strong> — AI will verify:
    Hardness HRC ≤ 22 &nbsp;·&nbsp;
    HIC Test (NACE TM0284) &nbsp;·&nbsp;
    SSC Test (NACE TM0177) &nbsp;·&nbsp;
    Chemical limits for sour service
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="nace-off">
    ⚪ <strong>NACE OFF</strong> — Standard review only (no sour service check)
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── Review Button ──────────────────────────────────
if uploaded:
    file_bytes = uploaded.read()
    file_size  = len(file_bytes)

    if file_size > 5 * 1024 * 1024:
        st.error(f"❌ File too large: {round(file_size/1024/1024,1)} MB. Maximum is 5 MB.")
        st.info("💡 Compress at smallpdf.com or ilovepdf.com")
        st.stop()

    st.caption(f"📄 {uploaded.name} — {round(file_size/1024, 1)} KB")

    if st.button("🔍 Review Certificate", type="primary", use_container_width=True):

        with st.spinner("AI is reviewing the certificate... (20–40 sec)"):

            b64_data = base64.standard_b64encode(file_bytes).decode()
            fname    = uploaded.name.lower()

            if fname.endswith(".pdf"):
                block = {"type":"document","source":{"type":"base64","media_type":"application/pdf","data":b64_data}}
            elif fname.endswith((".jpg",".jpeg")):
                block = {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b64_data}}
            else:
                block = {"type":"image","source":{"type":"base64","media_type":"image/png","data":b64_data}}

            # Build NACE instruction
            if nace_required:
                nace_instruction = """
NACE MR0175 / ISO 15156 IS REQUIRED for this material (sour service / H2S environment).
You MUST check and report:
1. Hardness — must be HRC ≤ 22 (or HBW ≤ 237 or HV ≤ 248). If hardness exceeds limit → FAIL.
2. HIC Test (NACE TM0284) — check if HIC test was performed and results reported (CLR, CTR, CSR).
   - If HIC not tested → flag as MISSING.
   - If tested and passed → PASS. If failed → FAIL.
3. SSC Test (NACE TM0177) — check if SSC test was performed.
   - If SSC not tested → flag as MISSING.
   - If tested and passed → PASS. If failed → FAIL.
4. Chemical limits for sour service — check Sulfur ≤ 0.003% for HIC resistant grades.
5. If ANY NACE requirement FAILS or is MISSING → overall verdict must be FAIL or CONDITIONAL.
"""
            else:
                nace_instruction = """
NACE MR0175 / ISO 15156 is NOT required for this review.
Report NACE data if present in the certificate, but do not fail the certificate for missing NACE tests.
"""

            prompt = f"""Review this mill certificate carefully.
Identify the material standard automatically from the certificate.
Compare every chemical and mechanical value against the correct standard limits.

{nace_instruction}

Respond ONLY in valid JSON with no markdown fences, no extra text:
{{
  "standard": "full standard name e.g. ASTM A106 Grade B",
  "specification": "e.g. ASTM A106",
  "grade": "e.g. Grade B",
  "heat_number": "value or null",
  "lot_number": "value or null",
  "manufacturer": "value or null",
  "test_date": "value or null",
  "product_form": "e.g. Seamless Pipe",
  "size": "e.g. 4 inch SCH 40 or null",
  "verdict": "PASS or FAIL or CONDITIONAL",
  "chemical": {{
    "ELEMENT": {{"found": 0.0, "min": null, "max": 0.0, "status": "PASS or FAIL or MISSING"}}
  }},
  "mechanical": {{
    "PROPERTY": {{"found": 0, "min": 0, "max": null, "unit": "", "status": "PASS or FAIL or MISSING"}}
  }},
  "impact": {{
    "required": false,
    "temperature": null,
    "average_J": null,
    "required_J": null,
    "status": "PASS or FAIL or MISSING or NA"
  }},
  "nace": {{
    "required": true,
    "hardness_hrc": null,
    "hardness_limit": 22,
    "hardness_status": "PASS or FAIL or MISSING",
    "hic_tested": false,
    "hic_clr": null,
    "hic_ctr": null,
    "hic_csr": null,
    "hic_status": "PASS or FAIL or MISSING or NA",
    "ssc_tested": false,
    "ssc_status": "PASS or FAIL or MISSING or NA",
    "sulfur_sour": null,
    "overall_nace_status": "PASS or FAIL or CONDITIONAL or NA",
    "notes": "brief NACE compliance notes"
  }},
  "failed_items": [],
  "missing_items": [],
  "warnings": [],
  "summary": "One paragraph summary including NACE status if applicable"
}}"""

            try:
                client = anthropic.Anthropic(api_key=key, timeout=120.0)
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=3000,
                    system="""You are a senior materials engineer and NACE-certified corrosion specialist.
You review mill certificates against ASME, ASTM, API 5L, EN, GB/T standards
and NACE MR0175/ISO 15156 sour service requirements.
Be precise. Apply exact standard limits.""",
                    messages=[{"role":"user","content":[block,{"type":"text","text":prompt}]}]
                )

                raw = response.content[0].text.strip()
                if "```" in raw:
                    parts = raw.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("json"): part = part[4:]
                        part = part.strip()
                        if part.startswith("{"): raw = part; break

                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    raw = raw[start:end]

                result = json.loads(raw)
                result["_nace_required"] = nace_required
                st.session_state.result   = result
                st.session_state.filename = uploaded.name

            except json.JSONDecodeError as e:
                st.error(f"Could not parse AI response. Please try again. ({e})")
                st.stop()
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

# ── Show Results ───────────────────────────────────
if st.session_state.result:
    r            = st.session_state.result
    verdict      = r.get("verdict", "CONDITIONAL")
    nace_was_on  = r.get("_nace_required", False)

    st.divider()

    # Verdict
    if verdict == "PASS":
        st.markdown('<p class="pass">✅ PASS — Certificate Approved</p>', unsafe_allow_html=True)
    elif verdict == "FAIL":
        st.markdown('<p class="fail">❌ FAIL — Certificate Rejected</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="cond">⚠️ CONDITIONAL — Review Required</p>', unsafe_allow_html=True)

    # NACE verdict badge
    if nace_was_on:
        nace    = r.get("nace", {})
        nstatus = nace.get("overall_nace_status", "NA")
        if nstatus == "PASS":
            st.success("🛡️ NACE MR0175 / ISO 15156 — PASS")
        elif nstatus == "FAIL":
            st.error("🛡️ NACE MR0175 / ISO 15156 — FAIL")
        elif nstatus == "CONDITIONAL":
            st.warning("🛡️ NACE MR0175 / ISO 15156 — CONDITIONAL")
        else:
            st.warning("🛡️ NACE MR0175 / ISO 15156 — NOT VERIFIED")

    # Document info
    cols = st.columns(4)
    for col, (label, val) in zip(cols, [
        ("Standard",     r.get("standard","—")),
        ("Heat No.",     r.get("heat_number","—")),
        ("Manufacturer", r.get("manufacturer","—")),
        ("Test Date",    r.get("test_date","—")),
    ]):
        with col:
            st.markdown(f'<div class="label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{val or "—"}</div>', unsafe_allow_html=True)

    st.markdown("")
    cols2 = st.columns(4)
    for col, (label, val) in zip(cols2, [
        ("Grade",        r.get("grade","—")),
        ("Product Form", r.get("product_form","—")),
        ("Size",         r.get("size","—")),
        ("Lot No.",      r.get("lot_number","—")),
    ]):
        with col:
            st.markdown(f'<div class="label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{val or "—"}</div>', unsafe_allow_html=True)

    st.divider()

    # ── Tabs ──────────────────────────────────────
    if nace_was_on:
        tab1, tab2, tab3, tab4 = st.tabs(["🧪 Chemistry", "⚙️ Mechanical", "❄️ Impact", "🛡️ NACE"])
    else:
        tab1, tab2, tab3 = st.tabs(["🧪 Chemistry", "⚙️ Mechanical", "❄️ Impact"])

    # Chemistry tab
    with tab1:
        st.markdown("#### 🧪 Chemical Composition (%)")
        chem = r.get("chemical", {})
        if chem:
            hc = st.columns([1,1,1,1,1.5])
            for h, label in zip(hc, ["El.","Found","Min","Max","Status"]):
                h.markdown(f"**{label}**")
            for el, v in chem.items():
                c = st.columns([1,1,1,1,1.5])
                c[0].write(f"`{el}`")
                c[1].write(str(v.get("found","—")))
                c[2].write(str(v.get("min","—")) if v.get("min") is not None else "—")
                c[3].write(str(v.get("max","—")) if v.get("max") is not None else "—")
                s = v.get("status","—")
                if s=="PASS":   c[4].success(s)
                elif s=="FAIL": c[4].error(s)
                else:           c[4].warning(s)
        else:
            st.info("No chemical data found")

    # Mechanical tab
    with tab2:
        st.markdown("#### ⚙️ Mechanical Properties")
        mech = r.get("mechanical", {})
        if mech:
            hm = st.columns([2,1,1,1,1,1.5])
            for h, label in zip(hm, ["Property","Found","Min","Max","Unit","Status"]):
                h.markdown(f"**{label}**")
            for prop, v in mech.items():
                c = st.columns([2,1,1,1,1,1.5])
                c[0].write(prop)
                c[1].write(str(v.get("found","—")))
                c[2].write(str(v.get("min","—")) if v.get("min") is not None else "—")
                c[3].write(str(v.get("max","—")) if v.get("max") is not None else "—")
                c[4].write(str(v.get("unit","")))
                s = v.get("status","—")
                if s=="PASS":   c[5].success(s)
                elif s=="FAIL": c[5].error(s)
                else:           c[5].warning(s)
        else:
            st.info("No mechanical data found")

    # Impact tab
    with tab3:
        st.markdown("#### ❄️ Impact Tests")
        imp = r.get("impact", {})
        if imp.get("required") and imp.get("status") != "NA":
            ci = st.columns(4)
            ci[0].metric("Temperature",   f"{imp.get('temperature','—')} °C")
            ci[1].metric("Average Energy", f"{imp.get('average_J','—')} J")
            ci[2].metric("Required",       f"{imp.get('required_J','—')} J")
            s = imp.get("status","—")
            ci[3].markdown("**Status**")
            if s=="PASS":   ci[3].success(s)
            elif s=="FAIL": ci[3].error(s)
            else:           ci[3].warning(s)
        else:
            st.info("Impact test not required or not found for this standard.")

    # NACE tab
    if nace_was_on:
        with tab4:
            nace = r.get("nace", {})
            st.markdown("#### 🛡️ NACE MR0175 / ISO 15156 Compliance")

            # Overall NACE status
            nstatus = nace.get("overall_nace_status","NA")
            if nstatus=="PASS":         st.success("✅ Overall NACE Status: PASS")
            elif nstatus=="FAIL":       st.error("❌ Overall NACE Status: FAIL")
            elif nstatus=="CONDITIONAL":st.warning("⚠️ Overall NACE Status: CONDITIONAL")
            else:                       st.warning("⚠️ Overall NACE Status: NOT VERIFIED")

            st.markdown("")
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Hardness Check**")
                hrc   = nace.get("hardness_hrc")
                hlim  = nace.get("hardness_limit", 22)
                hstat = nace.get("hardness_status","—")
                st.write(f"Measured HRC: **{hrc if hrc is not None else '—'}**")
                st.write(f"Limit HRC: **≤ {hlim}**")
                if hstat=="PASS":   st.success(f"Hardness: {hstat}")
                elif hstat=="FAIL": st.error(f"Hardness: {hstat}")
                else:               st.warning(f"Hardness: {hstat}")

                st.markdown("")
                st.markdown("**HIC Test (NACE TM0284)**")
                hic_s = nace.get("hic_status","—")
                clr   = nace.get("hic_clr")
                ctr   = nace.get("hic_ctr")
                csr   = nace.get("hic_csr")
                if clr is not None: st.write(f"CLR: {clr}%  (limit ≤15%)")
                if ctr is not None: st.write(f"CTR: {ctr}%  (limit ≤5%)")
                if csr is not None: st.write(f"CSR: {csr}%  (limit ≤2%)")
                if hic_s=="PASS":   st.success(f"HIC: {hic_s}")
                elif hic_s=="FAIL": st.error(f"HIC: {hic_s}")
                elif hic_s=="NA":   st.info("HIC: Not Required")
                else:               st.warning(f"HIC: {hic_s}")

            with col_b:
                st.markdown("**SSC Test (NACE TM0177)**")
                ssc_s = nace.get("ssc_status","—")
                if ssc_s=="PASS":   st.success(f"SSC: {ssc_s}")
                elif ssc_s=="FAIL": st.error(f"SSC: {ssc_s}")
                elif ssc_s=="NA":   st.info("SSC: Not Required")
                else:               st.warning(f"SSC: {ssc_s}")

                st.markdown("")
                st.markdown("**Sulfur (Sour Service)**")
                s_val = nace.get("sulfur_sour")
                st.write(f"S found: **{s_val if s_val is not None else '—'}%**")
                st.write("Limit for HIC resistant: **≤ 0.003%**")

                st.markdown("")
                st.markdown("**Notes**")
                st.info(nace.get("notes","No additional NACE notes."))

    # ── Issues ────────────────────────────────────
    failed   = r.get("failed_items", [])
    missing  = r.get("missing_items", [])
    warnings = r.get("warnings", [])

    st.divider()
    if failed or missing or warnings:
        st.markdown("#### 🚨 Issues Found")
        for item in failed:   st.error(f"❌ {item}")
        for item in missing:  st.warning(f"⚠️ {item}")
        for item in warnings: st.info(f"ℹ️ {item}")
    else:
        st.success("✅ No issues found — all values within specification")

    # ── Summary ───────────────────────────────────
    st.divider()
    st.markdown("#### 📝 Review Summary")
    st.info(r.get("summary",""))
    st.caption(f"File: {st.session_state.filename} · Reviewed by MatCert AI · {'NACE Required' if nace_was_on else 'Standard Review'}")

    # ── Bottom clear button ───────────────────────
    st.divider()
    if st.button("🔄 Clear & Review Another Certificate", use_container_width=True):
        st.session_state.result = None
        st.session_state.filename = ""
        st.session_state.uploader_key += 1
        st.rerun()
