# 1. Install Python deps
cd backend
pip install -r requirements.txt

# 2. Set your key
cp .env.example .env
# edit .env → paste your ANTHROPIC_API_KEY

# 3. Run the server
python app.py
# → http://localhost:5000

# 4. Open frontend/index.html in your browser
