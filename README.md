# MTC_AI_Validator
# MatCert — Streamlit Version

AI-powered material certificate reviewer. Upload a mill certificate (PDF or image)
and get an instant PASS / FAIL verdict against ASME, ASTM, Q355D, and NACE standards.

---

## Deploy on Streamlit Community Cloud (Free)

1. **Fork or push** this folder to a GitHub repository

2. **Go to** https://share.streamlit.io → Sign in with GitHub → **New app**

3. **Select** your repo, branch (`main`), and set the main file to `app.py`

4. **Before deploying**, click **Advanced settings → Secrets** and paste:
   ```
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
   Get your key at: https://console.anthropic.com/

5. Click **Deploy** — your public URL will be ready in ~1 minute

---

## Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your API key
mkdir .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml and paste your real ANTHROPIC_API_KEY

# Run the app
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Files

```
streamlit_matcert/
├── app.py                          # The entire application (one file)
├── requirements.txt                # Python dependencies
└── .streamlit/
    └── secrets.toml.example        # API key template
```

---

## Supported Standards

| Standard             | Description                       |
|----------------------|-----------------------------------|
| ASME A106 Gr.B / C  | Seamless carbon steel pipe        |
| ASTM A516 Gr.70     | Pressure vessel plates            |
| ASTM A333 Gr.6      | Low-temperature seamless pipe     |
| Q355D (GB/T 1591)   | Structural steel plates           |

Add more by editing the `STANDARDS` dictionary in `app.py`.
