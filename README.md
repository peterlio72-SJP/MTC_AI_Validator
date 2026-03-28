# MatCert Basic Agent v2.0
## Shared Standards Library Edition

---

## The Big Idea — One Library, Many Agents

```
📁 C:\shared_standards\          ← ONE shared folder
      ASME Section II Part A.pdf
      API 5L 46th Edition.pdf
      NACE MR0175.pdf
      GB-T 1591.pdf
              │
    ┌─────────┼──────────────┐
    ▼         ▼              ▼
🤖 Agent 1   🤖 Agent 2    🤖 Agent 3
MatCert      Weld Record    Datasheet
Reviewer     Checker        Validator
```

All agents read from the **same folder**.
Update a standard once → all agents use the new version instantly.

---

## What the Agent Does

```
Drop certificate into inbox/ folder
              ↓  (10 seconds)
🔍  Reads certificate → identifies standard
📚  Searches shared standards folder
              ↓
     Found? → reads your PDF for exact limits
     Not found? → uses AI built-in knowledge
              ↓
🔬  Reviews all values → PASS / FAIL
📊  Saves to Excel tracker
📧  Sends email (if configured)
📱  Sends WhatsApp (if configured)
📁  Moves file to processed/
```

---

## Setup

### Step 1 — Install Python
Download from https://python.org (version 3.9+)

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Create shared standards folder
Create a folder anywhere on your computer (or network drive):
```
Windows:     C:\shared_standards\
Mac/Linux:   /Users/yourname/shared_standards/
Network:     \\server\engineering\standards\
```

Drop your standard PDFs in there:
```
shared_standards/
  ├── ASME Section II Part A.pdf
  ├── API 5L 46th Edition.pdf
  ├── NACE MR0175.pdf
  └── GB-T 1591 Q355D.pdf
```

### Step 4 — Configure .env
```bash
cp .env.example .env
```
Open `.env` in Notepad and set:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
STANDARDS_DIR=C:\shared_standards
```

### Step 5 — Run
```bash
python agent.py
```

You will see:
```
📚 Shared library loaded: 4 standard(s) from C:\shared_standards
   • ASME Section II Part A.pdf  (12,450 KB, modified 2024-01-15)
   • API 5L 46th Edition.pdf     (8,230 KB, modified 2023-11-20)
   ...
✅ Agent running — drop certificates into inbox/
```

### Step 6 — Drop a certificate
Copy any mill certificate PDF or image into the `inbox/` folder.
The agent processes it within 10 seconds.

---

## Folder Structure

```
matcert_agent/
├── agent.py              ← run this
├── requirements.txt
├── .env                  ← your keys + STANDARDS_DIR path
├── inbox/                ← DROP CERTIFICATES HERE ⭐
├── processed/            ← reviewed files land here
├── failed/               ← error files land here
├── standards/            ← local fallback (if STANDARDS_DIR blank)
└── reports/
    ├── matcert_tracker.xlsx    ← all reviews in one Excel file
    └── cert_name_timestamp.json ← individual JSON results
```

---

## Adding Another Agent Later

Any future agent (weld record checker, datasheet validator, etc.)
just needs one line in its own `.env`:

```
STANDARDS_DIR=C:\shared_standards
```

That's it — it immediately has access to all your standards.

---

## Adding New Standards

Just drop a PDF into your shared folder.
The agent reloads the library every 10 seconds automatically.
No restart needed.

---

## Excel Tracker Columns

| Column | Description |
|---|---|
| Timestamp | When reviewed |
| Filename | Certificate filename |
| Standard | e.g. ASTM A106 |
| Grade | e.g. Grade B |
| Heat No. | From certificate |
| Manufacturer | From certificate |
| Verdict | PASS / FAIL / CONDITIONAL |
| Source | Library Document or AI Knowledge |
| Confidence | HIGH / MEDIUM / LOW |
| Library File Used | Which standard PDF was used |
| Failed Items | List of out-of-spec values |
| Missing Items | Required values not found |
| Summary | AI generated summary |

---

## Cost per review
~$0.01–0.03 per certificate · $5 credit ≈ 150–500 reviews
