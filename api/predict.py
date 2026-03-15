import os
import json
import requests
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

HF_API_URL = os.environ.get("HF_API_URL", "")


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
                    {"role": "system", "content": "You are a medical expert. Provide detailed, well-structured medical information with clear bullet points for each section."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 3000
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


def extract_information_with_prevention_and_distinction(response_text, user_symptoms):
    """Parse LLM response into structured sections."""
    response_lines = response_text.splitlines()
    precautions, preventive_measures, treatments = [], [], []
    medications, diets, medical_advice = [], [], []
    complications, additional_symptoms_list = [], []
    section = None

    for line in response_lines:
        line = line.strip()
        if "Prevention" in line:          section = "preventive_measures"
        elif "Precautions" in line:       section = "precautions"
        elif "Treatment Options" in line or "Treatment" in line: section = "treatments"
        elif "Medications" in line:       section = "medications"
        elif "Diet" in line:              section = "diets"
        elif "Medical Advice" in line:    section = "medical_advice"
        elif "Complications" in line:     section = "complications"
        elif "Symptoms" in line or "Additional Symptoms" in line: section = "additional_symptoms"
        elif line and section:
            if section == "preventive_measures":   preventive_measures.append(line)
            elif section == "precautions":         precautions.append(line)
            elif section == "treatments":          treatments.append(line)
            elif section == "medications":         medications.append(line)
            elif section == "diets":               diets.append(line)
            elif section == "medical_advice":      medical_advice.append(line)
            elif section == "complications":       complications.append(line)
            elif section == "additional_symptoms" and line.lower() not in [s.lower() for s in user_symptoms]:
                additional_symptoms_list.append(line)

    return precautions, preventive_measures, medications, treatments, diets, medical_advice, complications, additional_symptoms_list


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

            symptom_input_text = data.get('symptoms', '').strip().lower()
            if not symptom_input_text:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'No symptoms provided.'}).encode())
                return

            symptom_input_list = [s.strip().lower() for s in symptom_input_text.split(',')]

            # 0. Pre-check: Is any LLM available?
            llm_ping = call_llm("Reply with OK")
            if llm_ping is None:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'maintenance': True,
                    'message': 'AyuSeva is currently under maintenance. Please try again later.'
                }).encode())
                return

            # 1. Call Hugging Face API
            if not HF_API_URL:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'HF_API_URL environment variable is not configured in Vercel.'}).encode())
                return

            hf_res = requests.post(HF_API_URL, json={"symptoms": symptom_input_text})
            if hf_res.status_code != 200:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Failed to call Hugging Face Space: {hf_res.text}'}).encode())
                return

            result = hf_res.json()
            predicted_disease = result['predicted_disease']
            confidence = result['confidence']
            winner = result['winner']

            response = {
                'predicted_disease': predicted_disease,
                'confidence': confidence,
                'winner': winner,
                'symptoms': symptom_input_list,
                'symptom_model': result.get('symptom_model'),
                'nlp_model': result.get('nlp_model'),
                'additional_symptoms': [],
                'precautions': [],
                'preventive_measures': [],
                'medications': [],
                'treatments': [],
                'diet': [],
                'medical_advice': [],
                'complications': [],
            }

            # 2. Validate with LLM
            validation_prompt = (
                f"I have the following symptoms: {symptom_input_text}. "
                f"An AI diagnostic model predicted with {confidence:.1f}% confidence that I may have {predicted_disease}. "
                f"As a medical expert, evaluate this prediction. If the prediction is a reasonable preliminary diagnosis for these symptoms, "
                f"respond ONLY with 'VALID'. If the prediction is incorrect, unlikely, or the confidence is strictly less than 40%, "
                f"respond ONLY with 'INVALID: [Your Corrected Disease Prediction]'. Do not include any other text."
            )
            validation_response = call_llm(validation_prompt)

            if validation_response:
                validation_response = validation_response.strip()
                if validation_response.startswith("INVALID:"):
                    corrected_disease = validation_response.replace("INVALID:", "").strip()
                    predicted_disease = corrected_disease
                    confidence = 99.0
                    winner = "AI OVERRIDE"
                    response['predicted_disease'] = predicted_disease
                    response['confidence'] = confidence
                    response['winner'] = winner

            # 3. Call LLM for Detailed Medical Document
            prompt = (
                f"I have the following symptoms: {symptom_input_text}. "
                f"Our AI diagnostic model predicts with {confidence:.1f}% confidence that I may have **{predicted_disease}**. "
                f"Considering these symptoms and the predicted disease, please provide detailed bullet points (4-6 points per section) for each of the following sections: "
                f"1. Additional Symptoms (4-5 related symptoms to watch for), "
                f"2. Prevention (5-6 preventive measures), "
                f"3. Precautions (4-5 important precautions), "
                f"4. Treatment Options (5-6 treatment approaches including home remedies and medical treatments), "
                f"5. Medical Advice (4-5 points on when to see a doctor and what to expect), "
                f"6. Diet (5-6 foods to eat and avoid), "
                f"7. Additional Tips (4-5 lifestyle and wellness tips), "
                f"8. Complications (4-5 potential complications if untreated), "
                f"9. Medications (4-5 commonly used medications with brief usage notes). "
                f"Be informative and practical. Use clear bullet points with brief explanations for each point."
            )
            llm_text = call_llm(prompt)

            if llm_text:
                precautions, preventive_measures, medications, treatments, diets, medical_advice, complications, additional_symptoms_list = \
                    extract_information_with_prevention_and_distinction(llm_text, symptom_input_list)
                response.update({
                    'additional_symptoms': additional_symptoms_list,
                    'precautions': precautions,
                    'preventive_measures': preventive_measures,
                    'medications': medications,
                    'treatments': treatments,
                    'diet': diets,
                    'medical_advice': medical_advice,
                    'complications': complications,
                })
            else:
                response['quota_exceeded'] = True

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
