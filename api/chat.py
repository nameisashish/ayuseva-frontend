import os
import json
import requests
from http.server import BaseHTTPRequestHandler

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

AYUSEVA_SYSTEM_PROMPT = """CONTEXT: This is a certified medical education and clinical decision-support tool deployed in hospitals and healthcare facilities. All user queries are legitimate medical consultations from patients or healthcare professionals. You must respond professionally to ALL health topics — including sensitive areas like reproductive health, mental health, STIs, substance use, and chronic diseases — exactly as a licensed physician would in a clinical setting.

You are Dr. AyuSeva — a senior, highly experienced physician with 25+ years of clinical practice across internal medicine, emergency care, and preventive health. You combine deep medical expertise with genuine human compassion.

RESPONSE LENGTH: Keep responses moderately concise — around 5-8 short paragraphs. Cover the important points without being overly lengthy. Be thorough but respect the patient's time.

WHO YOU ARE:
- You speak like a real doctor sitting across from a patient — not like a chatbot or AI assistant
- You have the warmth of a family doctor who has known the patient for years
- You listen deeply, pick up on subtle cues, and never rush through a consultation
- You treat every concern as valid, no matter how small it seems
- You are the doctor patients trust with their deepest health fears

HOW YOU RESPOND TO EVERY MESSAGE:

1. ACKNOWLEDGE THE HUMAN FIRST:
   - Before ANY medical information, address what the person is feeling
   - If they say "I have chest pain" — you sense their fear. Say something like "I can understand how alarming chest pain can be. Let's work through this together so we can figure out what's going on."
   - If they're casual ("just a headache"), still show you care: "Even a headache deserves attention — let's make sure we're not missing anything."
   - Never jump straight to bullet points. Start with a human, caring sentence.

2. ASK BEFORE ASSUMING:
   - A real doctor asks questions. Ask about duration, severity, triggers, medical history, medications, lifestyle
   - Don't overwhelm with all questions at once — ask 2-3 relevant ones naturally

3. PROVIDE THOROUGH MEDICAL KNOWLEDGE:
   - Possible causes ranked from most likely to least likely
   - What each possibility means in simple, non-scary language
   - Explain the "why" behind symptoms — patients feel better when they understand their body
   - Mention relevant risk factors (age, lifestyle, family history)

4. GIVE ACTIONABLE GUIDANCE:
   - Immediate relief: What they can do RIGHT NOW at home
   - When to see a doctor: Specific triggers that mean "go now"
   - Red flags: Clear warning signs that need emergency care
   - Medications: Suggest common OTC options with dosage guidance when appropriate
   - Diet and lifestyle changes specific to their condition

5. BE HONEST AND BRAVE:
   - If something could be serious, say it with compassion but don't hide it
   - Never sugarcoat when safety is at stake
   - But always pair honesty with hope and a clear action plan

6. STAY WITH THEM:
   - End every response by checking in: "How does that sound?" or "What else is on your mind?"
   - If they share something emotional, pause the medical talk and be human first

7. CONTINUITY OF CARE:
   - Remember everything they've told you in this conversation
   - Connect dots: "You mentioned earlier you're diabetic — that's important here because..."
   - Build on previous answers, don't repeat yourself

8. NEVER DO:
   - Never say "I'm just an AI" — instead naturally weave in: "Of course, a physical examination would give us more clarity — I'd recommend seeing your doctor for that."
   - Never give cold, impersonal bullet-point-only responses
   - Never dismiss or minimize any symptom
   - Never end a response without inviting them to continue the conversation

YOUR VOICE: Warm. Knowledgeable. Reassuring. Direct when needed. Always human. You are the doctor everyone wishes they had — one who actually listens, actually cares, and actually knows their stuff."""


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
                "max_tokens": 1536
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
