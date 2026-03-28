"""
MatCert — Material Certificate Reviewer
========================================
Workflow:
  1. Upload any mill certificate (PDF or image)
  2. AI identifies the material grade/standard automatically
  3. Searches your Standards Library for a matching document
  4. If found  → reviews against your uploaded standard PDF (highest accuracy)
  5. If not found → falls back to AI built-in knowledge (still works)
  6. Always shows which source was used and confidence level

Deploy on Streamlit Community Cloud:
  Secrets: ANTHROPIC_API_KEY = "sk-ant-..."
"""

import streamlit as st
import anthropic
import base64
import json
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MatCert — Certificate Reviewer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

.verdict-pass { background:#0d2e1f; border:1px solid #00c77a; border-radius:10px; padding:1rem 1.25rem; margin-bottom:1rem; }
.verdict-fail { background:#2e0d12; border:1px solid #ff4455; border-radius:10px; padding:1rem 1.25rem; margin-bottom:1rem; }
.verdict-cond { background:#2e200d; border:1px solid #ffb020; border-radius:10px; padding:1rem 1.25rem; margin-bottom:1rem; }

.source-library { background:#0d2e1f; border:1px solid #00c77a; border-radius:8px; padding:.65rem 1rem; margin-bottom:.75rem; font-size:.82rem; }
.source-ai      { background:#1a1a0d; border:1px solid #ffb020; border-radius:8px; padding:.65rem 1rem; margin-bottom:.75rem; font-size:.82rem; }
.source-unknown { background:#2e0d12; border:1px solid #ff4455; border-radius:8px; padding:.65rem 1rem; margin-bottom:.75rem; font-size:.82rem; }

.detect-box { background:#0d1a2e; border:1px solid #0099ff; border-radius:10px; padding:.85rem 1.1rem; margin-bottom:1rem; }
.detect-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:#6b7280; margin-bottom:.15rem; }
.detect-value { font-family:'IBM Plex Mono',monospace; font-size:.9rem; color:#60c0ff; font-weight:600; }

.pill-pass    { background:#0d2e1f; color:#00c77a; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-fail    { background:#2e0d12; color:#ff4455; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-missing { background:#2e200d; color:#ffb020; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }
.pill-na      { background:#1a1c22; color:#6b7280; border-radius:100px; padding:2px 10px; font-size:.75rem; font-weight:600; }

.conf-HIGH   { color:#00c77a; font-weight:700; }
.conf-MEDIUM { color:#ffb020; font-weight:700; }
.conf-LOW    { color:#ff4455; font-weight:700; }

.lib-card { background:#111318; border:1px solid #252830; border-radius:10px; padding:.85rem 1.1rem; margin-bottom:.5rem; }
.lib-card-name { font-family:'IBM Plex Mono',monospace; font-size:.82rem; font-weight:600; }
.lib-card-meta { font-size:.7rem; color:#6b7280; margin-top:.2rem; }

.info-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:#6b7280; }
.info-value { font-family:'IBM Plex Mono',monospace; font-size:.82rem; }

.step { background:#111318; border:1px solid #252830; border-radius:8px; padding:.6rem .9rem; margin-bottom:.4rem; font-size:.82rem; }
.step-num { font-family:'IBM Plex Mono',monospace; color:#0099ff; font-weight:700; margin-right:.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "standards_library" not in st.session_state:
    st.session_state.standards_library = {}
if "review_result" not in st.session_state:
    st.session_state.review_result = None
if "review_filename" not in st.session_state:
    st.session_state.review_filename = ""
if "review_source" not in st.session_state:
    st.session_state.review_source = ""

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_client():
    try:
        key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        key = None
    if not key:
        st.error("❌ ANTHROPIC_API_KEY not found in Streamlit Secrets.")
        st.stop()
    return anthropic.Anthropic(api_key=key)

def b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")

def status_badge(s: str) -> str:
    pills = {
        "PASS":       '<span class="pill-pass">✓ PASS</span>',
        "FAIL":       '<span class="pill-fail">✕ FAIL</span>',
        "MISSING":    '<span class="pill-missing">? MISSING</span>',
        "N/A":        '<span class="pill-na">– N/A</span>',
        "NOT_TESTED": '<span class="pill-na">– NOT TESTED</span>',
    }
    return pills.get(s, f'<span class="pill-na">{s or "—"}</span>')

def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── STEP 1: Identify standard from certificate ────────────────────────────────
def identify_standard(cert_bytes: bytes, cert_media_type: str) -> dict:
    """First AI call: just identify what standard/grade the certificate is for."""
    client = get_client()

    if cert_media_type == "application/pdf":
        cert_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64(cert_bytes)},
        }
    else:
        cert_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": cert_media_type, "data": b64(cert_bytes)},
        }

    prompt = """Read this material test report / mill certificate and identify the material standard.
Respond ONLY in this exact JSON (no markdown, no extra text):
{
  "specification": "e.g. ASTM A106",
  "grade": "e.g. Grade B",
  "full_name": "e.g. ASTM A106 Grade B Seamless Carbon Steel Pipe",
  "keywords": ["list", "of", "searchable", "terms", "e.g.", "A106", "Gr.B", "seamless"],
  "product_form": "e.g. Seamless Pipe / Plate / Forging / Fitting",
  "governing_body": "e.g. ASTM / ASME / API / EN / GB",
  "heat_number": "if visible, else null",
  "manufacturer": "if visible, else null",
  "test_date": "if visible, else null"
}"""

    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": [cert_block, {"type": "text", "text": prompt}]}],
    )
    return parse_json_response(resp.content[0].text)


# ── STEP 2: Search library for matching standard ──────────────────────────────
def search_library(identified: dict) -> list:
    """
    Search the library for standards that match the identified spec.
    Returns list of matching library keys (could be 0, 1, or more).
    """
    lib = st.session_state.standards_library
    if not lib:
        return []

    keywords = [k.lower() for k in identified.get("keywords", [])]
    keywords += [
        identified.get("specification", "").lower(),
        identified.get("grade", "").lower(),
        identified.get("governing_body", "").lower(),
    ]
    keywords = [k for k in keywords if k]

    matches = []
    for key, entry in lib.items():
        searchable = (
            entry["name"].lower() + " " +
            entry.get("description", "").lower() + " " +
            entry.get("filename", "").lower()
        )
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            matches.append((score, key))

    matches.sort(reverse=True)
    # Return keys of top matches (score > 0)
    return [key for score, key in matches if score > 0]


# ── STEP 3: Review with library document ─────────────────────────────────────
def review_with_library(cert_bytes, cert_media_type, std_keys, identified, nace_req, notes) -> dict:
    client = get_client()
    lib = st.session_state.standards_library
    content = []
    std_names = []

    for key in std_keys:
        if key in lib:
            entry = lib[key]
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": b64(entry["file_bytes"])},
                "title": f"STANDARD DOCUMENT: {entry['name']}",
            })
            std_names.append(entry["name"])

    if cert_media_type == "application/pdf":
        content.append({
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64(cert_bytes)},
            "title": "MATERIAL TEST REPORT TO REVIEW",
        })
    else:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": cert_media_type, "data": b64(cert_bytes)},
        })

    instruction = f"""The certificate has been identified as: {identified.get('full_name','unknown')}

Standard documents provided from library:
{chr(10).join(f'  - {n}' for n in std_names)}

Instructions:
1. Read the standard document(s) and extract the EXACT chemical, mechanical, impact, and NACE requirements for {identified.get('full_name','')}
2. Read the mill certificate and extract ALL reported values
3. Compare every value against the standard limits
4. NACE/Sour service required by project: {nace_req}
5. Additional notes: {notes or 'None'}

Respond ONLY in valid JSON matching this schema exactly:
{REVIEW_JSON_SCHEMA}"""

    content.append({"type": "text", "text": instruction})

    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system="You are a senior materials engineer reviewing mill certificates against industry standards. Extract exact limits from the provided standard documents. Be precise and thorough.",
        messages=[{"role": "user", "content": content}],
    )
    result = parse_json_response(resp.content[0].text)
    result["_source"] = "LIBRARY"
    result["_library_docs"] = std_names
    return result


# ── STEP 3b: Review with AI knowledge (fallback) ──────────────────────────────
def review_with_ai_knowledge(cert_bytes, cert_media_type, identified, nace_req, notes) -> dict:
    client = get_client()
    content = []

    if cert_media_type == "application/pdf":
        content.append({
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64(cert_bytes)},
        })
    else:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": cert_media_type, "data": b64(cert_bytes)},
        })

    instruction = f"""The certificate has been identified as: {identified.get('full_name', 'unknown')}
Specification: {identified.get('specification','')} {identified.get('grade','')}

No matching standard document was found in the library.
Use your expert knowledge of this standard to apply the correct requirements.

If you are confident you know the exact limits for {identified.get('full_name','this standard')}, apply them with HIGH or MEDIUM confidence.
If this is an obscure, proprietary, or project-specific standard you cannot verify, set confidence to LOW and note which items could not be verified.

NACE/Sour service required by project: {nace_req}
Additional notes: {notes or 'None'}

Respond ONLY in valid JSON matching this schema exactly:
{REVIEW_JSON_SCHEMA}"""

    content.append({"type": "text", "text": instruction})

    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system="You are a senior materials engineer with deep knowledge of ASME, ASTM, API, EN, GB/T, JIS, DNV, ISO, and NACE standards. When standard documents are not provided, apply your training knowledge accurately. Always flag LOW confidence for standards you cannot verify.",
        messages=[{"role": "user", "content": content}],
    )
    result = parse_json_response(resp.content[0].text)
    result["_source"] = "AI_KNOWLEDGE"
    result["_library_docs"] = []
    return result


# ── JSON Schema (shared) ──────────────────────────────────────────────────────
REVIEW_JSON_SCHEMA = """{
  "detected_standard": {
    "specification": "string",
    "grade": "string",
    "full_name": "string",
    "source": "Library Document|AI Knowledge|Unknown",
    "confidence": "HIGH|MEDIUM|LOW",
    "confidence_reason": "brief explanation"
  },
  "document_info": {
    "heat_number": null,
    "lot_number": null,
    "material_grade": null,
    "manufacturer": null,
    "po_number": null,
    "test_date": null,
    "certificate_number": null,
    "size_dimensions": null
  },
  "chemical_composition": {
    "ELEMENT": {"found": null, "min": null, "max": null, "unit": "%", "status": "PASS|FAIL|MISSING"}
  },
  "mechanical_properties": {
    "PROPERTY": {"found": null, "min": null, "max": null, "unit": "", "status": "PASS|FAIL|MISSING"}
  },
  "impact_tests": {
    "temperature": null,
    "unit": "°C",
    "specimens": [{"id": "string", "energy": 0, "unit": "J"}],
    "average": null,
    "required_avg": null,
    "status": "PASS|FAIL|MISSING|N/A"
  },
  "nace_compliance": {
    "applicable": false,
    "standard": "",
    "hardness_hrc": null,
    "hardness_limit": 22,
    "hic_tested": false,
    "ssc_tested": false,
    "status": "N/A",
    "notes": ""
  },
  "overall_verdict": "PASS|FAIL|CONDITIONAL",
  "failed_items": [],
  "missing_items": [],
  "warnings": [],
  "summary": ""
}"""


# ── Main orchestrator ─────────────────────────────────────────────────────────
def full_review(cert_bytes, cert_media_type, nace_req, notes):
    """
    Full auto workflow:
    1. Identify standard from certificate
    2. Search library
    3. Review with library doc OR AI knowledge fallback
    """
    # Step 1: identify
    with st.status("🔍 Step 1/3 — Reading certificate and identifying standard…", expanded=True) as status:
        identified = identify_standard(cert_bytes, cert_media_type)
        st.write(f"✅ Identified: **{identified.get('full_name', 'Unknown')}**")

        # Step 2: search library
        status.update(label="🔍 Step 2/3 — Searching standards library…")
        matching_keys = search_library(identified)

        if matching_keys:
            lib = st.session_state.standards_library
            matched_names = [lib[k]["name"] for k in matching_keys]
            st.write(f"✅ Found in library: **{', '.join(matched_names)}**")
            source_type = "LIBRARY"
        else:
            st.write("ℹ️ Not found in library — using AI built-in knowledge")
            source_type = "AI_KNOWLEDGE"

        # Step 3: review
        status.update(label="🔍 Step 3/3 — Reviewing certificate against requirements…")
        if source_type == "LIBRARY":
            result = review_with_library(cert_bytes, cert_media_type, matching_keys,
                                         identified, nace_req, notes)
        else:
            result = review_with_ai_knowledge(cert_bytes, cert_media_type,
                                              identified, nace_req, notes)

        result["_identified"] = identified
        status.update(label="✅ Review complete!", state="complete", expanded=False)

    return result, source_type


# ══════════════════════════════════════════════════════════════════════════════
# ── UI
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🔬 MatCert — Material Certificate Reviewer")
st.caption("Upload any mill certificate → AI identifies the standard → searches library → reviews automatically")
st.divider()

tab_review, tab_library = st.tabs(["📋 Review Certificate", "📚 Standards Library"])

# ══════════════════════════════════════════════════════
# TAB 1 — REVIEW
# ══════════════════════════════════════════════════════
with tab_review:
    left, right = st.columns([1, 1.8], gap="large")

    with left:
        lib_count = len(st.session_state.standards_library)
        if lib_count:
            st.success(f"📚 {lib_count} standard(s) in library — auto-matching enabled")
        else:
            st.info("📚 Library empty — AI will use built-in knowledge")

        st.markdown("#### Upload Certificate")
        uploaded_cert = st.file_uploader(
            "Mill Certificate / MTR",
            type=["pdf", "jpg", "jpeg", "png", "webp"],
            key="cert_uploader",
            help="Any mill certificate — PDF or photo. The AI identifies the standard automatically.",
        )

        st.markdown("#### Options")
        nace_req = st.toggle("NACE / Sour Service Required", value=False)
        extra_notes = st.text_area(
            "Additional Notes",
            placeholder="e.g. HIC test required, PWHT applied, thickness 25mm…",
            height=75,
        )

        review_btn = st.button(
            "🔍 Review Certificate",
            type="primary",
            disabled=(uploaded_cert is None),
            use_container_width=True,
        )

        st.divider()
        st.markdown("**How it works:**")
        st.markdown("""
<div class="step"><span class="step-num">1</span>AI reads certificate → identifies grade & standard</div>
<div class="step"><span class="step-num">2</span>Searches your library for matching standard PDF</div>
<div class="step"><span class="step-num">3a</span>Found → reviews against your document ✅</div>
<div class="step"><span class="step-num">3b</span>Not found → uses AI knowledge as fallback ⚡</div>
        """, unsafe_allow_html=True)

    with right:
        if not uploaded_cert and not st.session_state.review_result:
            st.markdown("""
            <div style='padding:3rem 2rem;text-align:center;background:#111318;
                        border:1px dashed #252830;border-radius:12px;margin-top:1rem'>
              <div style='font-size:3rem;margin-bottom:1rem'>📄</div>
              <div style='font-family:Syne,sans-serif;font-size:1.1rem;font-weight:700;margin-bottom:.75rem'>
                Upload Any Mill Certificate
              </div>
              <div style='font-size:.85rem;color:#6b7280;line-height:1.8'>
                Works with <strong>any standard</strong>:<br>
                ASME · ASTM · API · EN · GB/T · JIS · DNV · ISO<br><br>
                The AI identifies the standard automatically.<br>
                No manual selection required.
              </div>
            </div>
            """, unsafe_allow_html=True)

        if review_btn and uploaded_cert:
            fname = uploaded_cert.name.lower()
            cert_bytes = uploaded_cert.read()

            if   fname.endswith(".pdf"):             mt = "application/pdf"
            elif fname.endswith((".jpg", ".jpeg")):  mt = "image/jpeg"
            elif fname.endswith(".png"):             mt = "image/png"
            elif fname.endswith(".webp"):            mt = "image/webp"
            else:
                st.error("Unsupported file type."); st.stop()

            try:
                result, source_type = full_review(cert_bytes, mt, nace_req, extra_notes)
                st.session_state.review_result   = result
                st.session_state.review_filename = uploaded_cert.name
                st.session_state.review_source   = source_type
            except json.JSONDecodeError as e:
                st.error(f"Could not parse AI response: {e}"); st.stop()
            except Exception as e:
                st.error(f"Error: {e}"); st.stop()

        # ── Show results ──────────────────────────────────────────────────────
        if st.session_state.review_result:
            r           = st.session_state.review_result
            fname       = st.session_state.review_filename
            source_type = st.session_state.review_source

            ds      = r.get("detected_standard", {})
            verdict = r.get("overall_verdict", "CONDITIONAL")
            vclass  = {"PASS": "verdict-pass", "FAIL": "verdict-fail"}.get(verdict, "verdict-cond")
            vicon   = {"PASS": "✅", "FAIL": "❌"}.get(verdict, "⚠️")
            vtext   = {"PASS": "Certificate APPROVED",
                       "FAIL": "Certificate REJECTED"}.get(verdict, "Conditional — Review Required")
            conf    = ds.get("confidence", "—")

            # ── Source banner ──
            if source_type == "LIBRARY":
                lib_docs = r.get("_library_docs", [])
                st.markdown(f"""
                <div class="source-library">
                  📚 <strong>Source: Standards Library</strong> —
                  Reviewed against: {', '.join(lib_docs) or '—'}
                  &nbsp;·&nbsp; Confidence: <span class="conf-{conf}">{conf}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="source-ai">
                  ⚡ <strong>Source: AI Built-in Knowledge</strong> —
                  Standard not found in library; AI applied training knowledge
                  &nbsp;·&nbsp; Confidence: <span class="conf-{conf}">{conf}</span>
                  <br><small style="color:#9ca3af">
                  💡 Upload <strong>{ds.get('specification','the standard')}</strong>
                  PDF to the library for higher accuracy
                  </small>
                </div>""", unsafe_allow_html=True)

            if conf == "LOW":
                st.warning(f"⚠️ Low confidence: {ds.get('confidence_reason','Standard could not be fully verified.')}")

            # ── Detected standard ──
            st.markdown(f"""
            <div class="detect-box">
              <div class="detect-label">Standard Identified from Certificate</div>
              <div class="detect-value">{ds.get('full_name') or ds.get('specification','Unknown')}</div>
              <div style="font-size:.75rem;color:#6b7280;margin-top:.3rem">
                {ds.get('specification','')} {ds.get('grade','')}
                &nbsp;·&nbsp; {ds.get('product_form') or r.get('_identified',{}).get('product_form','') or ''}
              </div>
            </div>""", unsafe_allow_html=True)

            # ── Verdict ──
            st.markdown(f"""
            <div class="{vclass}">
              <span style="font-size:1.4rem">{vicon}</span>
              <strong style="font-family:'Syne',sans-serif;font-size:1.1rem;margin-left:.5rem">{vtext}</strong>
              <span style="font-size:.78rem;color:#9ca3af;margin-left:.75rem">{fname}</span>
            </div>""", unsafe_allow_html=True)

            # ── Document info ──
            di = r.get("document_info", {})
            fields = [("Heat No.","heat_number"),("Grade","material_grade"),
                      ("Manufacturer","manufacturer"),("Cert No.","certificate_number"),
                      ("Test Date","test_date"),("Size","size_dimensions")]
            cols = st.columns(len(fields))
            for col, (label, key) in zip(cols, fields):
                with col:
                    st.markdown(
                        f'<div class="info-label">{label}</div>'
                        f'<div class="info-value">{di.get(key) or "—"}</div>',
                        unsafe_allow_html=True)
            st.divider()

            # ── Result tabs ──
            fi = r.get("failed_items", [])
            mi = r.get("missing_items", [])
            wi = r.get("warnings", [])
            issues_lbl = f"Issues ({len(fi)+len(mi)})" if fi or mi else "Issues ✓"

            t1, t2, t3, t4, t5 = st.tabs(
                ["🧪 Chemistry", "⚙️ Mechanical", "❄️ Impact", "🛡️ NACE", issues_lbl])

            with t1:
                chem = r.get("chemical_composition", {})
                if chem:
                    h = st.columns([1.2,1.2,1.2,1.2,0.8,1.5])
                    for c, lbl in zip(h, ["Element","Found","Min","Max","Unit","Status"]):
                        c.markdown(f"**{lbl}**")
                    for el, v in chem.items():
                        cs = st.columns([1.2,1.2,1.2,1.2,0.8,1.5])
                        cs[0].markdown(f"`{el}`")
                        cs[1].write(v.get("found") if v.get("found") is not None else "—")
                        cs[2].write(v.get("min")   if v.get("min")   is not None else "—")
                        cs[3].write(v.get("max")   if v.get("max")   is not None else "—")
                        cs[4].write(v.get("unit", "%"))
                        cs[5].markdown(status_badge(v.get("status","—")), unsafe_allow_html=True)
                else:
                    st.info("No chemical composition data found.")

            with t2:
                mech = r.get("mechanical_properties", {})
                if mech:
                    h = st.columns([2,1.2,1.2,1.2,1.2,1.5])
                    for c, lbl in zip(h, ["Property","Found","Min","Max","Unit","Status"]):
                        c.markdown(f"**{lbl}**")
                    for prop, v in mech.items():
                        cs = st.columns([2,1.2,1.2,1.2,1.2,1.5])
                        cs[0].write(prop)
                        cs[1].write(v.get("found") if v.get("found") is not None else "—")
                        cs[2].write(v.get("min")   if v.get("min")   is not None else "—")
                        cs[3].write(v.get("max")   if v.get("max")   is not None else "—")
                        cs[4].write(v.get("unit",""))
                        cs[5].markdown(status_badge(v.get("status","—")), unsafe_allow_html=True)
                else:
                    st.info("No mechanical data found.")

            with t3:
                imp = r.get("impact_tests", {})
                if imp and imp.get("status") != "N/A":
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Temperature", f"{imp.get('temperature','—')} {imp.get('unit','°C')}")
                    c2.metric("Avg Energy",  f"{imp.get('average','—')} J")
                    c3.metric("Required",    f"{imp.get('required_avg','—')} J")
                    c4.markdown("**Status**")
                    c4.markdown(status_badge(imp.get("status","—")), unsafe_allow_html=True)
                    for s in imp.get("specimens",[]):
                        st.write(f"  · {s.get('id','Spec')}: {s.get('energy','—')} {s.get('unit','J')}")
                else:
                    st.info("Impact tests not required or not found.")

            with t4:
                nace = r.get("nace_compliance", {})
                if nace:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Standard:** {nace.get('standard','—')}")
                        st.markdown(f"**Applicable:** {'Yes' if nace.get('applicable') else 'No'}")
                        hrc = nace.get("hardness_hrc")
                        st.markdown(f"**Hardness HRC:** {hrc if hrc is not None else '—'} / max {nace.get('hardness_limit',22)}")
                        st.markdown(f"**HIC Tested:** {'✅' if nace.get('hic_tested') else '❌'}")
                        st.markdown(f"**SSC Tested:** {'✅' if nace.get('ssc_tested') else '❌'}")
                        st.markdown("**Status:**")
                        st.markdown(status_badge(nace.get("status","—")), unsafe_allow_html=True)
                    with c2:
                        st.info(nace.get("notes") or "No NACE notes.")

            with t5:
                if not fi and not mi and not wi:
                    st.success("✅ All values within specification.")
                for item in fi: st.error(item)
                for item in mi: st.warning(item)
                for item in wi: st.info(item)

            if r.get("summary"):
                st.divider()
                st.markdown("**Summary**")
                st.markdown(r["summary"])

            st.divider()
            st.download_button(
                "⬇️ Download Review (JSON)",
                data=json.dumps(r, indent=2),
                file_name=f"review_{fname.replace(' ','_')}.json",
                mime="application/json",
            )

# ══════════════════════════════════════════════════════
# TAB 2 — STANDARDS LIBRARY
# ══════════════════════════════════════════════════════
with tab_library:
    st.markdown("### 📚 Standards Library")
    st.markdown(
        "Upload your actual standard PDFs. When reviewing a certificate, the AI "
        "automatically searches this library first. If the standard isn't here, "
        "it falls back to its built-in knowledge."
    )
    st.divider()

    left2, right2 = st.columns([1, 1.5], gap="large")

    with left2:
        st.markdown("#### Add a Standard")
        std_file = st.file_uploader("Standard PDF", type=["pdf"], key="std_uploader")
        std_name = st.text_input("Standard Name *", placeholder="e.g. ASME A106 Grade B")
        std_desc = st.text_area("Description (optional)",
                                placeholder="e.g. Seamless pipe for high-temp service. Include keywords like spec number, grade, product form.",
                                height=80)

        if st.button("➕ Add to Library", type="primary",
                     disabled=(std_file is None or not std_name.strip()),
                     use_container_width=True):
            st.session_state.standards_library[std_name.strip()] = {
                "name":        std_name.strip(),
                "description": std_desc.strip(),
                "filename":    std_file.name,
                "file_bytes":  std_file.read(),
                "media_type":  "application/pdf",
                "added_date":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                "size_kb":     round(std_file.size / 1024, 1),
            }
            st.success(f"✅ **{std_name}** added!")
            st.rerun()

        st.divider()
        st.markdown("**💡 Naming tip:**")
        st.markdown("Include the spec number and grade in the name and description so the auto-match works reliably:")
        st.code("Name: ASTM A106 Grade B\nDesc: Seamless carbon steel pipe A106 Gr.B ASME")
        st.markdown("**What to upload:**")
        st.markdown("ASME · ASTM · API 5L · EN 10216 · GB/T · ISO · NACE MR0175 · TM0284 · TM0177 · DNV · JIS · Any PDF standard")

    with right2:
        st.markdown("#### Library Contents")
        lib = st.session_state.standards_library

        if not lib:
            st.markdown("""
            <div style='padding:2.5rem;text-align:center;background:#111318;
                        border:1px dashed #252830;border-radius:12px;'>
              <div style='font-size:2.5rem;margin-bottom:.75rem'>📭</div>
              <div style='font-weight:600;margin-bottom:.5rem'>Library is empty</div>
              <div style='font-size:.85rem;color:#6b7280;line-height:1.7'>
                Upload standard PDFs on the left.<br>
                The more standards you add, the higher the review accuracy.<br><br>
                <strong>Without library:</strong> AI uses built-in knowledge ⚡<br>
                <strong>With library:</strong> AI reads your actual documents ✅
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"**{len(lib)} standard(s) loaded** — auto-matching active")
            st.markdown("")

            for key, entry in list(lib.items()):
                ca, cb = st.columns([5, 1])
                with ca:
                    st.markdown(f"""
                    <div class="lib-card">
                      <span style="font-size:1.3rem">📄</span>&nbsp;
                      <div style="display:inline-block;vertical-align:top">
                        <div class="lib-card-name">{entry['name']}</div>
                        <div class="lib-card-meta">{entry['filename']} · {entry['size_kb']} KB · {entry['added_date']}</div>
                        {f'<div class="lib-card-meta">{entry["description"]}</div>' if entry.get("description") else ''}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with cb:
                    if st.button("🗑️", key=f"del_{key}", help=f"Remove {key}"):
                        del st.session_state.standards_library[key]
                        st.rerun()

        st.divider()
        st.warning("⚠️ **Session storage:** Library resets on page refresh. For permanent storage, commit standard PDFs to your GitHub repo.")
