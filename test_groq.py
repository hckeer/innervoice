import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "Say hello in 5 words"}],
        max_tokens=50,
        temperature=0.7
    )
    print("SUCCESS:", response.choices[0].message.content)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e))
