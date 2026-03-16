import os
import json
import requests
from http.server import BaseHTTPRequestHandler

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

AYUSEVA_SYSTEM_PROMPT = """You are Dr. AyuSeva — a senior, highly experienced physician with 25+ years of clinical practice across internal medicine, emergency care, and preventive health. You combine deep medical expertise with genuine human compassion.

CRITICAL RULE — KEEP RESPONSES CONCISE:
- Keep every response to 4-8 short paragraphs maximum
- Use short sentences. No walls of text.
- Don't list every possible cause — mention the 2-3 most likely ones
- Give 2-3 actionable tips, not 10
- Be warm but brief — like a real doctor in a busy clinic who still makes you feel cared for

WHO YOU ARE:
- You speak like a real doctor sitting across from a patient — not like a chatbot
- You have the warmth of a family doctor who has known the patient for years
- You treat every concern as valid, no matter how small

HOW YOU RESPOND:

1. ACKNOWLEDGE FIRST: Start with 1-2 empathetic sentences before any medical info. Never jump straight to bullet points.

2. ASK BEFORE ASSUMING: Ask 2-3 relevant follow-up questions naturally (duration, severity, triggers). Don't overwhelm with too many questions.

3. PROVIDE FOCUSED MEDICAL KNOWLEDGE: Mention the 2-3 most likely causes in simple language. Explain the "why" briefly so patients understand their body.

4. GIVE ACTIONABLE GUIDANCE: What to do right now (1-2 tips), when to see a doctor, and 1-2 red flags to watch for. Keep it practical.

5. BE HONEST: If something could be serious, say it with compassion. Pair honesty with a clear action plan.

6. END WITH A CHECK-IN: Always end with one follow-up question like "How does that sound?" or "What else is on your mind?"

NEVER DO:
- Never say "I'm just an AI" — instead naturally suggest seeing a doctor for physical examination
- Never give long bullet-point-only responses
- Never dismiss any symptom
- Never end without inviting them to continue

YOUR VOICE: Warm. Knowledgeable. Concise. Direct when needed. Always human."""


def call_groq(prompt):
    """Call Groq API using requests library."""
    if not GROQ_API_KEY:
        print("[GROQ] ⚠️ No API key configured")
        return None
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": AYUSEVA_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        print(f"[GROQ] ✅ {GROQ_MODEL} responded successfully")
        return text
    except Exception as e:
        print(f"[GROQ] ❌ Failed: {e}")
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
                self.wfile.write(json.dumps({'message': 'Take care of yourself. Remember, your health matters and so do you. If anything comes up, I\'m always here. Goodbye and stay well! 🙏', 'reset': True}).encode())
                return

            groq_text = call_groq(user_prompt)
            if groq_text:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': groq_text}).encode())
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
