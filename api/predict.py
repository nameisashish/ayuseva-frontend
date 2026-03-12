import os
import json
import requests
import google.generativeai as gen_ai
from http.server import BaseHTTPRequestHandler

# Configure Gemini with the API Key securely stored in Vercel Environment Variables
gen_ai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
gemini_15 = gen_ai.GenerativeModel(model_name="gemini-1.5-flash")
gemini_25 = gen_ai.GenerativeModel(model_name="gemini-2.5-flash")
GEMINI_MODELS = [("gemini-1.5-flash", gemini_15), ("gemini-2.5-flash", gemini_25)]

HF_API_URL = os.environ.get("HF_API_URL", "") # URL of the Hugging Face Space (e.g. https://username-spacename.hf.space/predict)

def call_gemini(prompt):
    """Try gemini-1.5-flash first, fallback to gemini-2.5-flash, return None if both fail."""
    for model_name, model in GEMINI_MODELS:
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            continue
    return None

def extract_information_with_prevention_and_distinction(gemini_response_text, user_symptoms):
    """Parse Gemini response into structured sections."""
    response_lines = gemini_response_text.splitlines()
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

            # 1. Call Hugging Face API
            if not HF_API_URL:
                # If the user hasn't set the HF URL yet in Vercel, return a mock or error
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

            # 2. Validate with Gemini API
            validation_prompt = (
                f"I have the following symptoms: {symptom_input_text}. "
                f"An AI diagnostic model predicted with {confidence:.1f}% confidence that I may have {predicted_disease}. "
                f"As a medical expert, evaluate this prediction. If the prediction is a reasonable preliminary diagnosis for these symptoms, "
                f"respond ONLY with 'VALID'. If the prediction is incorrect, unlikely, or the confidence is strictly less than 40%, "
                f"respond ONLY with 'INVALID: [Your Corrected Disease Prediction]'. Do not include any other text."
            )
            validation_response = call_gemini(validation_prompt)
            
            if validation_response:
                validation_response = validation_response.strip()
                if validation_response.startswith("INVALID:"):
                    # Gemini has chosen to override the primary model
                    corrected_disease = validation_response.replace("INVALID:", "").strip()
                    predicted_disease = corrected_disease
                    confidence = 99.0
                    winner = "GEMINI OVERRIDE"
                    response['predicted_disease'] = predicted_disease
                    response['confidence'] = confidence
                    response['winner'] = winner

            # 3. Call Gemini API for Detailed Document
            prompt = (
                f"I have the following symptoms: {symptom_input_text}. "
                f"Our AI diagnostic model predicts with {confidence:.1f}% confidence that I may have **{predicted_disease}**. "
                f"Considering these symptoms and the predicted disease, please provide detailed, precise medical information including "
                f"Additional Symptoms, Prevention, Precautions, Treatment Options, Medical Advice, Diet, "
                f"Additional Tips, Complications, and Medications."
            )
            gemini_text = call_gemini(prompt)
            
            if gemini_text:
                precautions, preventive_measures, medications, treatments, diets, medical_advice, complications, additional_symptoms_list = \
                    extract_information_with_prevention_and_distinction(gemini_text, symptom_input_list)
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
