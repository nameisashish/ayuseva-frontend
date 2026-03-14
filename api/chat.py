import os
import json
import google.generativeai as gen_ai
from groq import Groq
from http.server import BaseHTTPRequestHandler

# Groq — primary LLM (free tier resets daily)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Gemini — fallback LLM
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
if GOOGLE_API_KEY:
    gen_ai.configure(api_key=GOOGLE_API_KEY)
gemini_15 = gen_ai.GenerativeModel(model_name="gemini-1.5-flash") if GOOGLE_API_KEY else None
gemini_25 = gen_ai.GenerativeModel(model_name="gemini-2.5-flash") if GOOGLE_API_KEY else None
GEMINI_MODELS = [(n, m) for n, m in [("gemini-1.5-flash", gemini_15), ("gemini-2.5-flash", gemini_25)] if m]

def call_gemini(prompt):
    # 1. Try Groq first
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            print(f"[GROQ] ✅ llama-3.3-70b-versatile responded successfully")
            return response.choices[0].message.content
        except Exception as e:
            print(f"[GROQ] ❌ Failed: {e}, falling back to Gemini...")

    # 2. Fallback to Gemini
    for model_name, model in GEMINI_MODELS:
        try:
            response = model.generate_content(prompt)
            print(f"[GEMINI] ✅ {model_name} responded successfully")
            return response.text
        except Exception as e:
            print(f"[GEMINI] ❌ {model_name} failed: {e}")
            continue
    print("[LLM] ⚠️ All models exhausted — returning None")
    return None

class handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            user_prompt = data.get('message', '').strip()
            if not user_prompt:
                 self.send_response(400)
                 self.end_headers()
                 self.wfile.write(json.dumps({'error': 'No message provided.'}).encode())
                 return

            if user_prompt.lower() in ('exit', 'quit', 'bye', 'goodbye'):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': 'Goodbye! Take Care 🙏', 'reset': True}).encode())
                return

            gemini_text = call_gemini(user_prompt)
            if gemini_text:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': gemini_text}).encode())
            else:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'The app is currently under maintenance. Please try again later.'}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
