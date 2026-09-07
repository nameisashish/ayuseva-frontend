# Groq Setup

Set GROQ_API_KEY in the Vercel project's environment variables for Production (and Preview if used). Redeploy after changing the value. For local development, export GROQ_API_KEY before starting the Python API server.

GROQ_API_KEY is the only required AI-provider setting. Do not paste the key into
source code, browser JavaScript, logs, or Git. No Gemini or OpenAI API key is used.

The app calls Groq at https://api.groq.com/openai/v1/chat/completions.
It uses openai/gpt-oss-120b, with openai/gpt-oss-20b as a bounded fallback when
Groq returns 403 or 404. The openai/ prefix is the model name, not the API provider.
See [Groq's supported models](https://console.groq.com/docs/models).

A valid key must belong to a Groq project with access to these models and
available quota. Changing a key cannot bypass account permissions or rate limits.
Errors distinguish missing configuration, authentication, model access, rate
limits, timeouts, and invalid responses. Provider response bodies and keys are
not logged by the Groq client.

Run offline regression tests from this repository root:

```sh
python3 -B -m unittest discover -s tests -v
```

Tests mock external services; deployment verification requires the hosted secret.

