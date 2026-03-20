import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("Testing openai/gpt-oss-120b...")
try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=100,
        temperature=0.7
    )
    content = response.choices[0].message.content
    print(f"Response: '{content}'")
    print(f"Length: {len(content) if content else 0}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\nTesting llama-3.3-70b-versatile...")
try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=100,
        temperature=0.7
    )
    content = response.choices[0].message.content
    print(f"Response: '{content}'")
    print(f"Length: {len(content) if content else 0}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
