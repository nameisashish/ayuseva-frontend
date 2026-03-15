import os
import json
import google.generativeai as gen_ai
from http.server import BaseHTTPRequestHandler

# --- Groq (Primary) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- Gemini (Fallback) ---
gen_ai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
gemini_15 = gen_ai.GenerativeModel(model_name="gemini-1.5-flash")
gemini_25 = gen_ai.GenerativeModel(model_name="gemini-2.5-flash")
GEMINI_MODELS = [("gemini-1.5-flash", gemini_15), ("gemini-2.5-flash", gemini_25)]


def call_groq(prompt):
    """Call Groq API. Returns response text or None on failure."""
    if not GROQ_API_KEY:
        print("[GROQ] ⚠️ No API key configured, skipping")
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            GROQ_URL,
            data=json.dumps({
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are AyuSeva, a helpful and knowledgeable medical assistant. Provide clear, detailed, and practical health advice."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2048
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            print(f"[GROQ] ✅ {GROQ_MODEL} responded successfully")
            return text
    except Exception as e:
        print(f"[GROQ] ❌ Failed: {e}")
        return None


def call_gemini(prompt):
    """Try Gemini models as fallback. Returns response text or None."""
    for model_name, model in GEMINI_MODELS:
        try:
            response = model.generate_content(prompt)
            print(f"[GEMINI] ✅ {model_name} responded successfully")
            return response.text
        except Exception as e:
            print(f"[GEMINI] ❌ {model_name} failed: {e}")
            continue
    print("[GEMINI] ⚠️ All models exhausted — returning None")
    return None


def call_llm(prompt):
    """Try Groq first, fall back to Gemini."""
    result = call_groq(prompt)
    if result:
        return result
    print("[LLM] ⚠️ Groq unavailable, falling back to Gemini...")
    return call_gemini(prompt)


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

            llm_text = call_llm(user_prompt)
            if llm_text:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': llm_text}).encode())
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
