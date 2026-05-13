"""
Groq API wrapper — runs Llama 3.1 8B, the production target model.
"""
import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    def __init__(self):
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.model = 'llama-3.1-8b-instant'
        self.max_tokens = 2000

    def call(self, system_prompt: str, user_message: str) -> str | None:
        retries = 3
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"LLM call failed (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None