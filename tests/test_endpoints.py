import io
import json
import unittest
from unittest.mock import Mock, patch

from api import chat, predict
from test_groq_service import response


def invoke(module, payload):
    request = object.__new__(module.handler)
    body = json.dumps(payload).encode()
    request.headers = {"Content-Length": str(len(body))}
    request.rfile = io.BytesIO(body)
    request.send_json = Mock()
    request.do_POST()
    request.send_json.assert_called_once()
    return request.send_json.call_args.args


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.hf = Mock(status_code=200)
        self.hf.json.return_value = {
            "predicted_disease": "Test condition", "confidence": 80.0, "winner": "NLP"
        }

    @patch.object(chat, "GROQ_API_KEY", "test-secret")
    @patch("groq_service.requests.post")
    def test_chat_model_fallback(self, post):
        post.side_effect = [response(404), response(content="Hello")]
        self.assertEqual(invoke(chat, {"message": "Hello"}), (200, {"message": "Hello"}))
        self.assertEqual(post.call_count, 2)

    @patch.object(chat, "GROQ_API_KEY", "test-secret")
    @patch("groq_service.requests.post")
    def test_chat_invalid_key(self, post):
        post.return_value = response(401)
        status, body = invoke(chat, {"message": "Hello"})
        self.assertEqual(status, 503)
        self.assertEqual(body["code"], "authentication")
        self.assertNotIn("message", body)

    @patch.object(predict, "GROQ_API_KEY", "test-secret")
    @patch("groq_service.requests.post")
    def test_predict_does_not_report_provider_failure_as_success(self, post):
        for replies, code in (
            ([self.hf, response(404), response(404)], "model_access"),
            ([self.hf, response(content="VALID"), response(429)], "rate_limit"),
        ):
            with self.subTest(code=code):
                post.side_effect = replies
                status, body = invoke(predict, {"symptoms": "test symptom"})
                self.assertEqual(status, 503)
                self.assertEqual(body["code"], code)
                self.assertNotIn("quota_exceeded", body)
                self.assertNotIn("predicted_disease", body)

    @patch.object(predict, "GROQ_API_KEY", "test-secret")
    @patch("groq_service.requests.post")
    def test_predict_success_and_section_parsing(self, post):
        post.side_effect = [
            self.hf, response(content="VALID"),
            response(content="Medical Advice\n- Consult a clinician.\nPrevention\n- Rest."),
        ]
        status, body = invoke(predict, {"symptoms": "test symptom"})
        self.assertEqual(status, 200)
        self.assertEqual(body["medical_advice"], ["- Consult a clinician."])
        self.assertEqual(body["preventive_measures"], ["- Rest."])
        self.assertEqual(post.call_args_list[1].kwargs["json"]["max_completion_tokens"], 2048)
        self.assertEqual(post.call_args_list[2].kwargs["json"]["max_completion_tokens"], 6144)

    def test_empty_input_is_rejected(self):
        for module, payload in ((chat, {"message": ""}), (predict, {"symptoms": ""})):
            with self.subTest(module=module.__name__):
                self.assertEqual(invoke(module, payload)[0], 400)
