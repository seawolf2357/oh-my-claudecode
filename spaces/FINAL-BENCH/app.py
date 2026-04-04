import os
import json
import requests
import gradio as gr

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/kimi-k2p5"


def chat(message, history):
    messages = []
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        if bot_msg:
            messages.append({"role": "assistant", "content": bot_msg})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": MODEL,
        "max_tokens": 4096,
        "top_p": 1,
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "temperature": 0.6,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
    }

    response = requests.post(API_URL, headers=headers, json=payload, stream=True)
    response.raise_for_status()

    partial = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data = line[len("data: "):]
        if data.strip() == "[DONE]":
            break
        chunk = json.loads(data)
        delta = chunk["choices"][0].get("delta", {})
        token = delta.get("content", "")
        if token:
            partial += token
            yield partial


demo = gr.ChatInterface(
    fn=chat,
    title="FINAL-BENCH",
    description="Kimi K2.5 (Fireworks AI)",
    examples=["Hello, how are you?", "Explain quantum computing in simple terms."],
    type="tuples",
)

if __name__ == "__main__":
    demo.launch()
