"""
Material Certificate Reviewer - Backend API
Flask application that uses Claude AI to review material certificates
against industry standards (ASME, ASTM, EN, NACE, etc.)

Requirements:
    pip install flask flask-cors anthropic pypdf2 pillow python-dotenv

Setup:
    1. Create a .env file with your ANTHROPIC_API_KEY
    2. Run: python app.py
    3. API will be available at http://localhost:5000
"""

import os
import base64
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ─── Anthropic Client ────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─── Standards Database ──────────────────────────────────────────────────────
STANDARDS = {
    "ASME_A106_GR_B": {
        "name": "ASME A106 Grade B Seamless Pipe",
        "chemical": {
            "C":  {"min": None, "max": 0.30, "unit": "%"},
            "Mn": {"min": 0.29, "max": 1.06, "unit": "%"},
            "P":  {"min": None, "max": 0.035, "unit": "%"},
            "S":  {"min": None, "max": 0.035, "unit": "%"},
            "Si": {"min": 0.10, "max": None,  "unit": "%"},
            "Cu": {"min": None, "max": 0.40, "unit": "%"},
            "Ni": {"min": None, "max": 0.40, "unit": "%"},
            "Cr": {"min": None, "max": 0.40, "unit": "%"},
            "Mo": {"min": None, "max": 0.15, "unit": "%"},
            "V":  {"min": None, "max": 0.08, "unit": "%"},
        },
        "mechanical": {
            "UTS":   {"min": 415, "max": None, "unit": "MPa"},
            "YS":    {"min": 240, "max": None, "unit": "MPa"},
            "Elongation": {"min": 30, "max": None, "unit": "%"},
        },
        "nace": "MR0175/ISO 15156 – HIC & SSC resistance required for sour service",
    },
    "ASME_A106_GR_C": {
        "name": "ASME A106 Grade C Seamless Pipe",
        "chemical": {
            "C":  {"min": None, "max": 0.35, "unit": "%"},
            "Mn": {"min": 0.29, "max": 1.06, "unit": "%"},
            "P":  {"min": None, "max": 0.035, "unit": "%"},
            "S":  {"min": None, "max": 0.035, "unit": "%"},
            "Si": {"min": 0.10, "max": None,  "unit": "%"},
        },
        "mechanical": {
            "UTS": {"min": 485, "max": None, "unit": "MPa"},
            "YS":  {"min": 275, "max": None, "unit": "MPa"},
            "Elongation": {"min": 30, "max": None, "unit": "%"},
        },
        "nace": "MR0175/ISO 15156 applicable for sour service environments",
    },
    "Q355D": {
        "name": "Q355D Structural Steel Plate (GB/T 1591)",
        "chemical": {
            "C":  {"min": None, "max": 0.20, "unit": "%"},
            "Mn": {"min": None, "max": 1.70, "unit": "%"},
            "Si": {"min": None, "max": 0.50, "unit": "%"},
            "P":  {"min": None, "max": 0.025, "unit": "%"},
            "S":  {"min": None, "max": 0.020, "unit": "%"},
            "Nb": {"min": None, "max": 0.07, "unit": "%"},
            "V":  {"min": None, "max": 0.20, "unit": "%"},
            "Ti": {"min": None, "max": 0.20, "unit": "%"},
            "Ceq":{"min": None, "max": 0.45, "unit": "%"},
        },
        "mechanical": {
            "YS":  {"min": 355, "max": None, "unit": "MPa"},
            "UTS": {"min": 470, "max": 630,  "unit": "MPa"},
            "Elongation": {"min": 22, "max": None, "unit": "%"},
        },
        "impact": {
            "temperature": -20,
            "energy_avg": {"min": 34, "unit": "J"},
            "unit": "°C",
        },
        "nace": "Not typically NACE-classified; check project-specific requirements",
    },
    "ASTM_A516_GR70": {
        "name": "ASTM A516 Grade 70 Pressure Vessel Plate",
        "chemical": {
            "C":  {"min": None, "max": 0.28, "unit": "%"},
            "Mn": {"min": 0.85, "max": 1.20, "unit": "%"},
            "P":  {"min": None, "max": 0.035, "unit": "%"},
            "S":  {"min": None, "max": 0.035, "unit": "%"},
            "Si": {"min": 0.15, "max": 0.40, "unit": "%"},
        },
        "mechanical": {
            "UTS": {"min": 485, "max": 620, "unit": "MPa"},
            "YS":  {"min": 260, "max": None, "unit": "MPa"},
            "Elongation": {"min": 17, "max": None, "unit": "%"},
        },
        "nace": "HIC testing per NACE TM0284 required for sour service; SSC per NACE TM0177",
    },
    "ASTM_A333_GR6": {
        "name": "ASTM A333 Grade 6 Low-Temperature Pipe",
        "chemical": {
            "C":  {"min": None, "max": 0.30, "unit": "%"},
            "Mn": {"min": 0.29, "max": 1.06, "unit": "%"},
            "P":  {"min": None, "max": 0.025, "unit": "%"},
            "S":  {"min": None, "max": 0.025, "unit": "%"},
            "Si": {"min": None, "max": None, "unit": "%"},
        },
        "mechanical": {
            "UTS": {"min": 415, "max": None, "unit": "MPa"},
            "YS":  {"min": 240, "max": None, "unit": "MPa"},
            "Elongation": {"min": 30, "max": None, "unit": "%"},
        },
        "impact": {
            "temperature": -45,
            "energy_avg": {"min": 20, "unit": "J"},
            "unit": "°C",
        },
        "nace": "Suitable for low-temperature applications; NACE per project specification",
    },
}

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert materials engineer and quality inspector specializing in:
- Material Test Reports (MTR) / Mill Certificates
- Industry standards: ASME, ASTM, EN, GB/T, API, ISO
- NACE corrosion standards (MR0175, TM0177, TM0284)
- Chemical composition analysis
- Mechanical property verification (UTS, YS, elongation, hardness)
- Impact test (Charpy/CVN) evaluation
- Weld procedure and heat treatment review

When reviewing a certificate, you MUST:
1. Extract ALL chemical composition values found in the document
2. Extract ALL mechanical test results (UTS, YS, elongation, reduction of area, hardness)
3. Extract impact test results if present (temperature, energy values, avg)
4. Compare each value against the provided standard limits
5. Flag any value that is out of specification with "FAIL"
6. Flag any missing required value as "MISSING"
7. Confirm passing values with "PASS"
8. Note NACE compliance status
9. Provide an overall PASS/FAIL verdict with clear reasoning

Always respond in valid JSON format matching this schema:
{
  "document_info": {
    "heat_number": "...",
    "lot_number": "...",
    "material_grade": "...",
    "manufacturer": "...",
    "po_number": "...",
    "test_date": "..."
  },
  "chemical_composition": {
    "Element": {"found": value_or_null, "min": value_or_null, "max": value_or_null, "unit": "%", "status": "PASS|FAIL|MISSING"}
  },
  "mechanical_properties": {
    "Property": {"found": value_or_null, "min": value_or_null, "max": value_or_null, "unit": "...", "status": "PASS|FAIL|MISSING"}
  },
  "impact_tests": {
    "temperature": value_or_null,
    "specimens": [{"id": "...", "energy": value, "unit": "J"}],
    "average": value_or_null,
    "required_avg": value_or_null,
    "status": "PASS|FAIL|MISSING|N/A"
  },
  "nace_compliance": {
    "applicable": true/false,
    "standard": "...",
    "hardness_hrc": value_or_null,
    "hardness_limit": 22,
    "hic_tested": true/false,
    "ssc_tested": true/false,
    "status": "PASS|FAIL|NOT_TESTED|N/A",
    "notes": "..."
  },
  "overall_verdict": "PASS|FAIL|CONDITIONAL",
  "failed_items": ["list of specific failures"],
  "missing_items": ["list of missing required items"],
  "warnings": ["non-critical observations"],
  "summary": "Brief human-readable summary paragraph"
}"""


# ─── Helper: Encode file to base64 ───────────────────────────────────────────
def encode_file(file_bytes: bytes, media_type: str) -> str:
    return base64.standard_b64encode(file_bytes).decode("utf-8")


# ─── Route: Health check ──────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Material Certificate Reviewer"})


# ─── Route: List available standards ─────────────────────────────────────────
@app.route("/standards", methods=["GET"])
def list_standards():
    return jsonify({
        key: {"name": val["name"], "nace": val.get("nace", "N/A")}
        for key, val in STANDARDS.items()
    })


# ─── Route: Review certificate ────────────────────────────────────────────────
@app.route("/review", methods=["POST"])
def review_certificate():
    """
    POST /review
    Form data:
      - file: PDF or image file (required)
      - standard: standard key from STANDARDS dict (required)
      - nace_required: "true"/"false" (optional, default false)
      - notes: additional reviewer notes (optional)
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    standard_key = request.form.get("standard", "ASME_A106_GR_B").upper().replace("-", "_")
    nace_required = request.form.get("nace_required", "false").lower() == "true"
    reviewer_notes = request.form.get("notes", "")

    if standard_key not in STANDARDS:
        return jsonify({
            "error": f"Unknown standard: {standard_key}",
            "available": list(STANDARDS.keys())
        }), 400

    standard = STANDARDS[standard_key]
    file_bytes = file.read()
    filename = file.filename.lower()

    # Determine media type
    if filename.endswith(".pdf"):
        media_type = "application/pdf"
        doc_type = "document"
    elif filename.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
        doc_type = "image"
    elif filename.endswith(".png"):
        media_type = "image/png"
        doc_type = "image"
    elif filename.endswith(".webp"):
        media_type = "image/webp"
        doc_type = "image"
    else:
        return jsonify({"error": "Unsupported file type. Use PDF, JPG, PNG, or WEBP"}), 400

    b64_data = encode_file(file_bytes, media_type)

    # Build the content blocks for Claude
    standard_context = f"""
STANDARD UNDER REVIEW: {standard['name']} ({standard_key})

CHEMICAL COMPOSITION LIMITS:
{json.dumps(standard.get('chemical', {}), indent=2)}

MECHANICAL PROPERTY LIMITS:
{json.dumps(standard.get('mechanical', {}), indent=2)}

IMPACT TEST REQUIREMENTS:
{json.dumps(standard.get('impact', {'note': 'Not required by this standard'}), indent=2)}

NACE REQUIREMENTS:
{standard.get('nace', 'Not specified')}
NACE Required by Project: {nace_required}

REVIEWER NOTES: {reviewer_notes if reviewer_notes else 'None'}

Please review the attached material certificate against ALL the above requirements and respond in the JSON schema specified.
"""

    if doc_type == "document":
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data
                }
            },
            {"type": "text", "text": standard_context}
        ]
    else:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data
                }
            },
            {"type": "text", "text": standard_context}
        ]

    # Call Claude API
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )

    raw_text = response.content[0].text

    # Parse JSON response
    try:
        # Strip markdown fences if present
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean)
    except json.JSONDecodeError:
        result = {"raw_response": raw_text, "parse_error": "Could not parse JSON"}

    return jsonify({
        "standard": standard_key,
        "standard_name": standard["name"],
        "filename": file.filename,
        "review": result
    })


# ─── Route: Multi-file batch review ──────────────────────────────────────────
@app.route("/batch-review", methods=["POST"])
def batch_review():
    """
    POST /batch-review (JSON body)
    {
      "certificates": [
        {"filename": "cert1.pdf", "data": "<base64>", "media_type": "application/pdf"},
        ...
      ],
      "standard": "ASME_A106_GR_B",
      "nace_required": false
    }
    """
    body = request.get_json()
    if not body or "certificates" not in body:
        return jsonify({"error": "Request body must include 'certificates' array"}), 400

    standard_key = body.get("standard", "ASME_A106_GR_B").upper()
    nace_required = body.get("nace_required", False)

    if standard_key not in STANDARDS:
        return jsonify({"error": f"Unknown standard: {standard_key}"}), 400

    standard = STANDARDS[standard_key]
    results = []

    for cert in body["certificates"]:
        try:
            media_type = cert["media_type"]
            b64_data = cert["data"]
            doc_type = "document" if media_type == "application/pdf" else "image"

            standard_context = f"""
STANDARD: {standard['name']} ({standard_key})
CHEMICAL LIMITS: {json.dumps(standard.get('chemical', {}))}
MECHANICAL LIMITS: {json.dumps(standard.get('mechanical', {}))}
IMPACT REQUIREMENTS: {json.dumps(standard.get('impact', {'note': 'Not required'}))}
NACE: {standard.get('nace', 'Not specified')} | Project NACE required: {nace_required}
Review this certificate and respond in the required JSON schema.
"""
            if doc_type == "document":
                content = [
                    {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
                    {"type": "text", "text": standard_context}
                ]
            else:
                content = [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
                    {"type": "text", "text": standard_context}
                ]

            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}]
            )

            raw_text = response.content[0].text
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            result = json.loads(clean)

            results.append({
                "filename": cert.get("filename", "unknown"),
                "status": "success",
                "review": result
            })

        except Exception as e:
            results.append({
                "filename": cert.get("filename", "unknown"),
                "status": "error",
                "error": str(e)
            })

    # Batch summary
    total = len(results)
    passed = sum(1 for r in results if r.get("review", {}).get("overall_verdict") == "PASS")
    failed = sum(1 for r in results if r.get("review", {}).get("overall_verdict") == "FAIL")

    return jsonify({
        "batch_summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": total - passed - failed
        },
        "results": results
    })


if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set. Create a .env file with your key.")
    else:
        print(f"✅ Anthropic API key loaded ({api_key[:8]}...)")
    print("🚀 Starting Material Certificate Reviewer API on http://localhost:5000")
    app.run(debug=True, port=5000)
