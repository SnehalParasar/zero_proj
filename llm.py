"""Swappable LLM client (Gemini + Groq)."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama3-70b-8192"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 2


class LLMClient:
    """Unified LLM interface backed by Gemini or Groq."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower().strip()
        print(f"[LLM] Using provider: {self.provider}")

        if self.provider == "gemini":
            import google.generativeai as genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            self._groq_client = None
        elif self.provider == "groq":
            from groq import Groq

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
            self._groq_client = Groq(api_key=api_key)
            self._gemini_model = None
        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER: {self.provider!r}. Use 'gemini' or 'groq'."
            )

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke the configured LLM and return plain text."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.provider == "gemini":
                    return self._call_gemini(system_prompt, user_prompt)
                return self._call_groq(system_prompt, user_prompt)
            except Exception as exc:  # noqa: BLE001 — retry on any provider failure
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_SLEEP_SECONDS)

        raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts") from last_error

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"{system_prompt.strip()}\n\n---\n\n{user_prompt.strip()}"
        response = self._gemini_model.generate_content(prompt)
        return (response.text or "").strip()

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        completion = self._groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (completion.choices[0].message.content or "").strip()
