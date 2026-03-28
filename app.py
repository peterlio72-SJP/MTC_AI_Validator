"""
MatCert Basic Agent — with Shared Standards Library
=====================================================
Watches an inbox folder for new certificate files.
Reads standards from a SHARED folder that any other
AI agent can also use for cross-reference.

Folder structure (recommended):

  C:/shared_standards/               ← shared by ALL agents
      ASME Section II Part A.pdf
      API 5L 46th Edition.pdf
      NACE MR0175.pdf
      GB-T 1591 Q355D.pdf

  C:/matcert_agent/                  ← this agent only
      agent.py
      .env
      inbox/                         ← drop certificates here
      processed/
      failed/
      reports/
          matcert_tracker.xlsx

Configure STANDARDS_DIR in .env to point to your shared folder.
"""

import os
import time
import base64
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

# Optional notifications
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("MatCertAgent")

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL       = os.getenv("NOTIFY_EMAIL", "")
TWILIO_SID         = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN       = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM        = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_TO          = os.getenv("TWILIO_WHATSAPP_TO", "")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

# ── Folder paths ──────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
INBOX_DIR     = BASE_DIR / "inbox"
PROCESSED_DIR = BASE_DIR / "processed"
FAILED_DIR    = BASE_DIR / "failed"
REPORTS_DIR   = BASE_DIR / "reports"
EXCEL_PATH    = REPORTS_DIR / "matcert_tracker.xlsx"

# ── Shared Standards Library ──────────────────────────────────────────────────
# Priority order:
#  1. STANDARDS_DIR in .env  (your shared network/local folder)
#  2. ./standards/           (local fallback next to agent.py)
_env_std_dir = os.getenv("STANDARDS_DIR", "").strip()
if _env_std_dir:
    STANDARDS_DIR = Path(_env_std_dir)
else:
    STANDARDS_DIR = BASE_DIR / "standards"

# Create all agent folders
for d in [INBOX_DIR, PROCESSED_DIR, FAILED_DIR, REPORTS_DIR,
          BASE_DIR / "standards"]:
    d.mkdir(exist_ok=True)

SUPPORTED_CERT_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_STD_EXT  = {".pdf"}

# ── AI client ─────────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")

def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def get_media_type(path: Path) -> str:
    return {
        ".pdf":  "application/pdf",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/pdf")

def make_block(data: bytes, media_type: str, title: str = None) -> dict:
    if media_type == "application/pdf":
        block = {"type": "document",
                 "source": {"type": "base64",
                            "media_type": media_type,
                            "data": b64(data)}}
        if title:
            block["title"] = title
        return block
    return {"type": "image",
            "source": {"type": "base64",
                       "media_type": media_type,
                       "data": b64(data)}}

# ── Shared Standards Library loader ──────────────────────────────────────────
def load_standards_library() -> dict:
    """
    Load PDFs from the shared standards folder.
    Any other AI agent pointing to the same folder
    gets the same up-to-date standards automatically.
    """
    library = {}

    if not STANDARDS_DIR.exists():
        log.warning(f"⚠️  Standards folder not found: {STANDARDS_DIR}")
        log.warning("    Create it and add standard PDFs, or set STANDARDS_DIR in .env")
        return library

    pdf_files = sorted(STANDARDS_DIR.glob("*.pdf"))
    if not pdf_files:
        log.info(f"📭 Standards folder is empty: {STANDARDS_DIR}")
        log.info("    AI will use built-in knowledge as fallback")
        return library

    for f in pdf_files:
        try:
            library[f.stem] = {
                "name":       f.stem,
                "filename":   f.name,
                "path":       str(f),
                "file_bytes": f.read_bytes(),
                "media_type": "application/pdf",
                "size_kb":    round(f.stat().st_size / 1024, 1),
                "modified":   datetime.fromtimestamp(
                                  f.stat().st_mtime).strftime("%Y-%m-%d"),
            }
        except Exception as e:
            log.warning(f"⚠️  Could not load {f.name}: {e}")

    log.info(f"📚 Shared library loaded: {len(library)} standard(s) from {STANDARDS_DIR}")
    for name, entry in library.items():
        log.info(f"   • {entry['filename']}  ({entry['size_kb']} KB,"
                 f" modified {entry['modified']})")
    return library

def search_library(identified: dict, library: dict) -> list:
    """Smart keyword search across library file names."""
    if not library:
        return []

    keywords = [k.lower() for k in identified.get("keywords", [])]
    keywords += [
        identified.get("specification", "").lower(),
        identified.get("grade", "").lower(),
        identified.get("governing_body", "").lower(),
    ]
    keywords = list({k for k in keywords if len(k) > 1})

    scores = []
    for key, entry in library.items():
        haystack = (entry["name"] + " " + entry["filename"]).lower()
        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scores.append((score, key))

    scores.sort(reverse=True)
    matched = [key for _, key in scores]

    if matched:
        log.info(f"   📚 Library matches: {matched}")
    else:
        log.info("   ⚡ No library match — will use AI built-in knowledge")

    return matched

# ── AI Prompts ────────────────────────────────────────────────────────────────
IDENTIFY_PROMPT = """Read this material test report / mill certificate.
Identify the material standard and grade.
Respond ONLY in JSON (no markdown, no extra text):
{
  "specification": "e.g. ASTM A106",
  "grade": "e.g. Grade B",
  "full_name": "e.g. ASTM A106 Grade B Seamless Carbon Steel Pipe",
  "governing_body": "e.g. ASTM",
  "product_form": "e.g. Seamless Pipe",
  "keywords": ["A106", "Gr.B", "seamless", "carbon", "pipe"],
  "heat_number": "value or null",
  "manufacturer": "value or null",
  "test_date": "value or null",
  "certificate_number": "value or null"
}"""

REVIEW_SCHEMA = """{
  "detected_standard": {
    "specification": "string",
    "grade": "string",
    "full_name": "string",
    "source": "Library Document|AI Knowledge",
    "library_file": "filename used or null",
    "confidence": "HIGH|MEDIUM|LOW",
    "confidence_reason": "string"
  },
  "document_info": {
    "heat_number": null, "lot_number": null,
    "material_grade": null, "manufacturer": null,
    "po_number": null, "test_date": null,
    "certificate_number": null, "size_dimensions": null
  },
  "chemical_composition": {
    "ELEMENT": {
      "found": null, "min": null, "max": null,
      "unit": "%", "status": "PASS|FAIL|MISSING"
    }
  },
  "mechanical_properties": {
    "PROPERTY": {
      "found": null, "min": null, "max": null,
      "unit": "", "status": "PASS|FAIL|MISSING"
    }
  },
  "impact_tests": {
    "temperature": null, "unit": "°C",
    "specimens": [{"id": "string", "energy": 0, "unit": "J"}],
    "average": null, "required_avg": null,
    "status": "PASS|FAIL|MISSING|N/A"
  },
  "nace_compliance": {
    "applicable": false, "standard": "",
    "hardness_hrc": null, "hardness_limit": 22,
    "hic_tested": false, "ssc_tested": false,
    "status": "N/A", "notes": ""
  },
  "overall_verdict": "PASS|FAIL|CONDITIONAL",
  "failed_items": [],
  "missing_items": [],
  "warnings": [],
  "summary": "string"
}"""

# ── Core AI calls ─────────────────────────────────────────────────────────────
def identify_certificate(file_bytes: bytes, media_type: str) -> dict:
    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": [
            make_block(file_bytes, media_type),
            {"type": "text", "text": IDENTIFY_PROMPT},
        ]}],
    )
    return parse_json(resp.content[0].text)


def review_certificate(file_bytes: bytes, media_type: str,
                        identified: dict, library: dict) -> dict:
    content  = []
    std_used = []

    # Attach matching standard documents from shared library
    for key in search_library(identified, library):
        entry = library[key]
        content.append(make_block(
            entry["file_bytes"], "application/pdf",
            title=f"STANDARD DOCUMENT: {entry['name']} (from shared library)"
        ))
        std_used.append(entry["filename"])

    # Attach the certificate
    content.append(make_block(file_bytes, media_type))

    # Build instruction
    if std_used:
        source_ctx = (
            f"Standard documents provided from shared library:\n"
            + "\n".join(f"  • {n}" for n in std_used)
            + f"\n\nRead these documents to extract EXACT chemical limits, "
              f"mechanical limits, impact requirements, and NACE clauses."
        )
        system = ("You are a senior materials engineer. "
                  "Extract exact requirements from the provided standard documents, "
                  "then compare against the mill certificate values precisely.")
    else:
        source_ctx = (
            "No matching standard found in the shared library. "
            "Use your expert knowledge of international standards "
            "(ASME, ASTM, API, EN, GB/T, ISO, NACE) to apply correct requirements."
        )
        system = ("You are a senior materials engineer with deep knowledge of "
                  "ASME, ASTM, API, EN, GB/T, JIS, DNV, ISO, and NACE standards.")

    instruction = f"""{source_ctx}

Certificate identified as: {identified.get('full_name', 'Unknown')}
Specification: {identified.get('specification','')} {identified.get('grade','')}

Review every value in the certificate against the standard requirements.
Respond ONLY in this exact JSON schema (no markdown):
{REVIEW_SCHEMA}"""

    content.append({"type": "text", "text": instruction})

    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    result = parse_json(resp.content[0].text)
    result["_source"]       = "LIBRARY" if std_used else "AI_KNOWLEDGE"
    result["_library_docs"] = std_used
    result["_standards_dir"]= str(STANDARDS_DIR)
    return result

# ── Excel Tracker ─────────────────────────────────────────────────────────────
HEADERS = [
    "Timestamp", "Filename", "Standard", "Grade",
    "Heat No.", "Manufacturer", "Test Date",
    "Verdict", "Source", "Confidence",
    "Library File Used", "Failed Items", "Missing Items", "Summary"
]
COL_WIDTHS = [18, 28, 16, 10, 14, 20, 12, 10, 14, 10, 30, 40, 30, 50]

def get_or_create_wb():
    if EXCEL_PATH.exists():
        return load_workbook(EXCEL_PATH)
    wb = Workbook()
    ws = wb.active
    ws.title = "Certificate Reviews"
    hfill = PatternFill("solid", fgColor="0A0C10")
    hfont = Font(bold=True, color="00D4AA", size=10)
    for col, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hfill; cell.font = hfont
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = COL_WIDTHS[col-1]
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    return wb

def append_to_excel(result: dict, filename: str):
    wb  = get_or_create_wb()
    ws  = wb.active
    ds  = result.get("detected_standard", {})
    di  = result.get("document_info", {})
    v   = result.get("overall_verdict", "CONDITIONAL")
    fi  = result.get("failed_items", [])
    mi  = result.get("missing_items", [])

    fills  = {"PASS":"0D2E1F","FAIL":"2E0D12","CONDITIONAL":"2E200D"}
    ffonts = {"PASS":"00C77A","FAIL":"FF4455","CONDITIONAL":"FFB020"}
    rfill  = PatternFill("solid", fgColor=fills.get(v,"1A1C22"))
    rfont  = Font(color=ffonts.get(v,"E8EAF0"), size=9)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        filename,
        ds.get("specification","—"),
        ds.get("grade","—"),
        di.get("heat_number") or "—",
        di.get("manufacturer") or "—",
        di.get("test_date") or "—",
        v,
        result.get("_source","—"),
        ds.get("confidence","—"),
        ", ".join(result.get("_library_docs",[])) or "None (AI Knowledge)",
        " | ".join(fi) or "None",
        " | ".join(mi) or "None",
        result.get("summary","")[:200],
    ]

    rn = ws.max_row + 1
    for col, val in enumerate(row, 1):
        cell = ws.cell(row=rn, column=col, value=val)
        cell.fill  = rfill; cell.font = rfont
        cell.alignment = Alignment(vertical="center", wrap_text=(col >= 12))
    ws.row_dimensions[rn].height = 18
    wb.save(EXCEL_PATH)
    log.info(f"📊 Excel updated: row {rn} → {EXCEL_PATH.name}")

# ── Optional Email ────────────────────────────────────────────────────────────
def send_email(result: dict, filename: str):
    if not EMAIL_AVAILABLE:
        return
    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFY_EMAIL]):
        return

    ds      = result.get("detected_standard", {})
    di      = result.get("document_info", {})
    v       = result.get("overall_verdict", "CONDITIONAL")
    fi      = result.get("failed_items", [])
    mi      = result.get("missing_items", [])
    emoji   = {"PASS":"✅","FAIL":"❌","CONDITIONAL":"⚠️"}.get(v,"⚠️")
    vcolor  = {"PASS":"#00c77a","FAIL":"#ff4455","CONDITIONAL":"#ffb020"}.get(v,"#ffb020")
    src     = "📚 Library: " + ", ".join(result.get("_library_docs",[])) \
              if result.get("_source") == "LIBRARY" else "⚡ AI Built-in Knowledge"

    def make_rows(items, color):
        if not items:
            return '<tr><td style="color:#9ca3af;padding:4px 8px">None</td></tr>'
        return "".join(
            f'<tr><td style="color:{color};padding:4px 8px">• {i}</td></tr>'
            for i in items)

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;background:#0a0c10;
            color:#e8eaf0;padding:24px;border-radius:12px;">
  <h2 style="margin-bottom:4px">🔬 MatCert Agent Report</h2>
  <p style="color:#6b7280;font-size:13px;margin-top:0">
    {datetime.now().strftime('%Y-%m-%d %H:%M')} · {filename}</p>

  <div style="background:#111318;border:1px solid #252830;border-radius:10px;
              padding:16px;margin:16px 0">
    <p style="margin:0 0 4px;font-size:11px;color:#6b7280;text-transform:uppercase">VERDICT</p>
    <p style="font-size:28px;font-weight:700;color:{vcolor};margin:0">{emoji} {v}</p>
  </div>

  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px">
    <tr><td style="color:#6b7280;padding:5px">Standard</td>
        <td style="font-family:monospace">{ds.get('full_name','—')}</td></tr>
    <tr style="background:#111318">
        <td style="color:#6b7280;padding:5px">Source</td>
        <td>{src}</td></tr>
    <tr><td style="color:#6b7280;padding:5px">Confidence</td>
        <td>{ds.get('confidence','—')}</td></tr>
    <tr style="background:#111318">
        <td style="color:#6b7280;padding:5px">Heat No.</td>
        <td style="font-family:monospace">{di.get('heat_number','—')}</td></tr>
    <tr><td style="color:#6b7280;padding:5px">Manufacturer</td>
        <td>{di.get('manufacturer','—')}</td></tr>
    <tr style="background:#111318">
        <td style="color:#6b7280;padding:5px">Standards Folder</td>
        <td style="font-family:monospace;font-size:11px">
            {result.get('_standards_dir','—')}</td></tr>
  </table>

  <h3 style="color:#ff4455;font-size:14px">❌ Failed</h3>
  <table style="width:100%;background:#111318;border-radius:8px;margin-bottom:12px">
    {make_rows(fi,'#ff4455')}</table>

  <h3 style="color:#ffb020;font-size:14px">⚠️ Missing</h3>
  <table style="width:100%;background:#111318;border-radius:8px;margin-bottom:12px">
    {make_rows(mi,'#ffb020')}</table>

  <div style="background:#111318;border:1px solid #252830;border-radius:8px;padding:12px">
    <p style="margin:0;font-size:13px;line-height:1.6;color:#9ca3af">
        {result.get('summary','')}</p></div>

  <p style="margin-top:16px;font-size:11px;color:#6b7280;text-align:center">
    MatCert Agent · Shared Standards: {STANDARDS_DIR}</p>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[MatCert] {emoji} {v} — {ds.get('specification','')} · {filename}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    if EXCEL_PATH.exists():
        with open(EXCEL_PATH,"rb") as f:
            part = MIMEBase("application","octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                'attachment; filename="matcert_tracker.xlsx"')
            msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            srv.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())
        log.info(f"📧 Email sent → {NOTIFY_EMAIL}")
    except Exception as e:
        log.error(f"📧 Email failed: {e}")

# ── Optional WhatsApp ─────────────────────────────────────────────────────────
def send_whatsapp(result: dict, filename: str):
    if not TWILIO_AVAILABLE or not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_TO]):
        return
    ds    = result.get("detected_standard", {})
    di    = result.get("document_info", {})
    v     = result.get("overall_verdict", "CONDITIONAL")
    fi    = result.get("failed_items", [])
    emoji = {"PASS":"✅","FAIL":"❌","CONDITIONAL":"⚠️"}.get(v,"⚠️")
    src   = "📚 Library" if result.get("_source") == "LIBRARY" else "⚡ AI Knowledge"

    msg = (
        f"🔬 *MatCert Agent*\n{'─'*28}\n"
        f"{emoji} *{v}*\n"
        f"📄 {filename}\n"
        f"📋 {ds.get('full_name','—')}\n"
        f"🔥 Heat: {di.get('heat_number','—')}\n"
        f"🏭 {di.get('manufacturer','—')}\n"
        f"📚 Source: {src}\n"
    )
    if fi:
        msg += "\n❌ *Failed:*\n" + "\n".join(f"  • {i}" for i in fi[:3])
        if len(fi) > 3:
            msg += f"\n  +{len(fi)-3} more"

    try:
        TwilioClient(TWILIO_SID, TWILIO_TOKEN).messages.create(
            body=msg, from_=TWILIO_FROM, to=TWILIO_TO)
        log.info(f"📱 WhatsApp sent → {TWILIO_TO}")
    except Exception as e:
        log.error(f"📱 WhatsApp failed: {e}")

# ── Process one file ──────────────────────────────────────────────────────────
def process_file(filepath: Path, library: dict):
    log.info(f"{'═'*55}")
    log.info(f"📄 New certificate: {filepath.name}")
    t0 = time.time()

    try:
        file_bytes = filepath.read_bytes()
        media_type = get_media_type(filepath)

        log.info("🔍 Step 1/3 — Identifying standard…")
        identified = identify_certificate(file_bytes, media_type)
        log.info(f"   → {identified.get('full_name','Unknown')}")

        log.info("📚 Step 2/3 — Searching shared library…")
        log.info(f"   → Library path: {STANDARDS_DIR}")

        log.info("🔬 Step 3/3 — Reviewing certificate…")
        result  = review_certificate(file_bytes, media_type, identified, library)
        verdict = result.get("overall_verdict","CONDITIONAL")
        fi      = result.get("failed_items",[])
        mi      = result.get("missing_items",[])
        log.info(f"   → Verdict: {verdict} | Failed: {len(fi)} | Missing: {len(mi)}")

        # Save outputs
        append_to_excel(result, filepath.name)
        send_email(result, filepath.name)
        send_whatsapp(result, filepath.name)

        # Save individual JSON
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = REPORTS_DIR / f"{filepath.stem}_{ts}.json"
        result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        log.info(f"💾 JSON saved: {result_file.name}")

        # Move to processed
        dest = PROCESSED_DIR / f"{ts}_{filepath.name}"
        shutil.move(str(filepath), str(dest))
        log.info(f"✅ Done in {time.time()-t0:.1f}s → moved to processed/")

    except Exception as e:
        log.error(f"❌ Failed: {e}")
        dest = FAILED_DIR / filepath.name
        try:
            shutil.move(str(filepath), str(dest))
        except Exception:
            pass
        log.info("   → Moved to failed/")

# ── Agent loop ────────────────────────────────────────────────────────────────
def run_agent():
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║     MatCert Basic Agent  v2.0                   ║")
    log.info("║     Shared Standards Library Edition            ║")
    log.info("╚══════════════════════════════════════════════════╝")
    log.info(f"📂 Inbox:           {INBOX_DIR.absolute()}")
    log.info(f"📚 Shared library:  {STANDARDS_DIR.absolute()}")
    log.info(f"📊 Excel tracker:   {EXCEL_PATH.absolute()}")
    log.info(f"⏱  Poll interval:   {POLL_INTERVAL}s")
    log.info(f"📧 Email:           {NOTIFY_EMAIL or 'not configured'}")
    log.info(f"📱 WhatsApp:        {'configured' if TWILIO_TO else 'not configured'}")
    log.info("─" * 52)
    log.info("✅ Agent running — drop certificates into inbox/")
    log.info("   Ctrl+C to stop")
    log.info("─" * 52)

    seen = set()

    while True:
        try:
            # Reload library each cycle — picks up newly added standards instantly
            library = load_standards_library()

            for fp in sorted(INBOX_DIR.iterdir()):
                if (fp.is_file()
                        and fp.suffix.lower() in SUPPORTED_CERT_EXT
                        and fp not in seen):
                    seen.add(fp)
                    process_file(fp, library)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log.info("\n🛑 Agent stopped")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        log.error("❌ ANTHROPIC_API_KEY not set in .env!")
    else:
        run_agent()
