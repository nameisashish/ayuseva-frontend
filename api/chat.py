import os
import json
import google.generativeai as gen_ai
from http.server import BaseHTTPRequestHandler

gen_ai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
gemini_15 = gen_ai.GenerativeModel(model_name="gemini-1.5-flash")
gemini_25 = gen_ai.GenerativeModel(model_name="gemini-2.5-flash")
GEMINI_MODELS = [("gemini-1.5-flash", gemini_15), ("gemini-2.5-flash", gemini_25)]

def call_gemini(prompt):
    for model_name, model in GEMINI_MODELS:
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            continue
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
