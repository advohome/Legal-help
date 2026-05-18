from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

unique_ips = set()

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    user_message = data.get("message", "")
    system_prompt = data.get("system", "Ты — юридический конструктор РФ. Начинай сразу с текста документа.")

    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.3,
                "max_tokens": 3000
            }
        )
        if r.status_code != 200:
            return jsonify({"error": f"Ошибка API: {r.status_code}"}), 500
        result = r.json()
        return jsonify({"result": result["choices"][0]["message"]["content"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/visit", methods=["POST"])
def visit():
    ip = request.remote_addr
    unique_ips.add(ip)
    return jsonify({"visitors": len(unique_ips)})

@app.route("/visitors", methods=["GET"])
def visitors():
    return jsonify({"visitors": len(unique_ips)})

@app.route("/")
def home():
    return "Server is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
