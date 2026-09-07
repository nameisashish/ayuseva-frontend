import unittest
from unittest.mock import Mock, patch

import requests
from groq_service import GROQ_MODELS, GROQ_URL, GroqError, complete


def response(status=200, content="Completed", finish="stop"):
    result = Mock(status_code=status)
    result.json.return_value = {
        "choices": [{"message": {"content": content}, "finish_reason": finish}]
    }
    return result


class GroqServiceTests(unittest.TestCase):
    def setUp(self):
        self.messages = [{"role": "user", "content": "private-test-prompt"}]
        self.patcher = patch("groq_service.requests.post")
        self.post = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.post.return_value = response()

    def test_groq_only_defaults_and_reasoning_budget(self):
        self.assertEqual(complete(" test-secret ", self.messages, 50), "Completed")
        args, kwargs = self.post.call_args
        self.assertEqual(args, (GROQ_URL,))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-secret")
        self.assertEqual(kwargs["json"]["model"], GROQ_MODELS[0])
        self.assertEqual(kwargs["json"]["messages"], self.messages)
        self.assertEqual(kwargs["json"]["max_completion_tokens"], 2048)
        self.assertFalse(kwargs["json"]["include_reasoning"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (5, 25))

    def test_missing_key_does_not_send_request(self):
        for key in ("", None, "  "):
            with self.subTest(key=key), self.assertRaises(GroqError) as caught:
                complete(key, self.messages)
            self.assertEqual(caught.exception.code, "configuration")
        self.post.assert_not_called()

    def test_model_access_falls_back(self):
        for status in (403, 404):
            with self.subTest(status=status):
                self.post.reset_mock()
                self.post.side_effect = [response(status), response()]
                self.assertEqual(complete("test-secret", self.messages), "Completed")
                self.assertEqual(
                    [call.kwargs["json"]["model"] for call in self.post.call_args_list],
                    list(GROQ_MODELS),
                )

    def test_model_fallback_is_bounded(self):
        self.post.side_effect = [response(404), response(404)]
        with self.assertRaises(GroqError) as caught:
            complete("test-secret", self.messages)
        self.assertEqual(caught.exception.code, "model_access")
        self.assertEqual(self.post.call_count, 2)

    def test_other_http_errors_do_not_retry(self):
        for status, code in ((401, "authentication"), (429, "rate_limit"),
                             (500, "unavailable"), (400, "unavailable"),
                             (302, "unavailable")):
            with self.subTest(status=status):
                self.post.reset_mock()
                self.post.return_value = response(status)
                with self.assertRaises(GroqError) as caught:
                    complete("test-secret", self.messages)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.post.call_count, 1)

    def test_transport_errors_are_safe_and_not_retried(self):
        for error, code in ((requests.Timeout("test-secret"), "timeout"),
                            (requests.ConnectionError("private-test-prompt"), "unavailable")):
            with self.subTest(code=code):
                self.post.reset_mock()
                self.post.side_effect = error
                with self.assertLogs("groq_service", level="WARNING") as logs:
                    with self.assertRaises(GroqError) as caught:
                        complete("test-secret", self.messages)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.post.call_count, 1)
                self.assertNotIn("test-secret", str(logs.output))
                self.assertNotIn("private-test-prompt", str(logs.output))

    def test_malformed_or_truncated_completions_are_rejected(self):
        malformed = response()
        malformed.json.return_value = {"choices": []}
        invalid_json = response()
        invalid_json.json.side_effect = ValueError("Invalid JSON")
        for result in (response(content=""), response(content=None),
                       response(finish="length"), malformed, invalid_json):
            with self.subTest(result=result):
                self.post.return_value = result
                with self.assertRaises(GroqError) as caught:
                    complete("test-secret", self.messages)
                self.assertEqual(caught.exception.code, "invalid_response")

    def test_provider_error_body_is_not_logged(self):
        self.post.return_value = response(401)
        self.post.return_value.text = "test-secret private-test-prompt"
        with self.assertLogs("groq_service", level="WARNING") as logs:
            with self.assertRaises(GroqError):
                complete("test-secret", self.messages)
        self.assertNotIn("test-secret", str(logs.output))
        self.assertNotIn("private-test-prompt", str(logs.output))
        self.post.return_value.json.assert_not_called()


if __name__ == "__main__":
    unittest.main()

