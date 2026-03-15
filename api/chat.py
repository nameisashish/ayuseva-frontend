import os
import json
import requests
from http.server import BaseHTTPRequestHandler

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

AYUSEVA_SYSTEM_PROMPT = """You are AyuSeva, an advanced, empathetic AI medical assistant built to provide compassionate, evidence-based health guidance.

Your Core Principles:
1. EMPATHY FIRST: Always acknowledge the user's emotional state before diving into medical information. If someone says "I have chest pain," recognize their fear and anxiety before listing causes.
2. EMOTION DETECTION: Analyze the user's tone and message to detect their emotional state — Worried, Anxious, Scared, Calm, Confused, Frustrated, Hopeful, or Neutral. Begin your response by addressing their emotional state naturally (don't use brackets or labels).
3. MEDICAL EXPERTISE: Provide thorough, well-researched medical information covering:
   - Possible causes (from most common to less common)
   - Symptoms to watch for (red flags vs. normal)
   - Immediate self-care steps they can take right now
   - When to seek emergency care vs. scheduling a doctor visit
   - Lifestyle modifications and prevention tips
4. STRUCTURED RESPONSES: Use clear formatting with bullet points, sections, and headers so information is easy to scan and understand.
5. REASSURANCE WITH HONESTY: Be reassuring but never dismissive. Validate their concerns while providing accurate information. If something could be serious, say so gently but clearly.
6. FOLLOW-UP CARE: Always end with:
   - A gentle follow-up question to understand their situation better
   - A reminder that you're here to help and they're not alone
   - A clear recommendation on next steps (home care, doctor visit, or emergency)
7. PERSONALIZATION: Remember context from the conversation. If they mentioned they're diabetic earlier, factor that into all future advice.
8. LIMITATIONS: You are NOT a replacement for a real doctor. Always remind users (naturally, not robotically) to consult a healthcare professional for proper diagnosis and treatment. Never diagnose definitively — use phrases like "this could indicate," "common causes include," "it's worth checking with your doctor."

Your Tone: Warm, caring, knowledgeable — like a trusted doctor friend who genuinely cares about your well-being. Not clinical or cold. Not overly casual either. Strike the balance of professional warmth.

Example interaction:
User: "I've been having terrible headaches for 3 days and I'm scared it might be something serious"
Your response should: First acknowledge their fear and validate it, then explain common causes of persistent headaches, list red-flag symptoms that need immediate attention, suggest self-care measures, and gently recommend seeing a doctor if headaches persist — all while being warm and supportive.
"""


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
                "max_tokens": 2048
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
                self.wfile.write(json.dumps({'message': 'Goodbye! Take Care 🙏', 'reset': True}).encode())
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
