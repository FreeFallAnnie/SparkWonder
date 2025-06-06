from flask import Flask, request, jsonify
import sqlite3
import os
import csv
import openai
from dotenv import load_dotenv
from flask import send_file

app = Flask(__name__)

@app.route("/play")
def play_page():
    return send_file("play.html")

# --- Setup ---

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY, organization=OPENAI_ORG_ID)

DB_PATH = "events.db"
CSV_PATH = "wondersparks.csv"

# --- Ensure database exists ---
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_text TEXT,
    ws_id INTEGER,
    full_prompt TEXT,
    response TEXT
)
""")
conn.commit()
conn.close()

# --- Helpers ---
def load_wondersparks():
    ws_map = {}
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ws_map[int(row['ID'])] = {
                "name": row['Name'],
                "prompt": row['Prompt'],
                "color": row['Color'].upper()
            }
    return ws_map


def ask_wonder(prompt_intro, ws_prompt, event_text):
    full_prompt = f"{prompt_intro} {ws_prompt} {event_text}"
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Respond clearly and creatively."},
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.7
    )
    return full_prompt, response.choices[0].message.content.strip()


def save_reflection(event_text, ws_id, full_prompt, response):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reflections (event_text, ws_id, full_prompt, response)
        VALUES (?, ?, ?, ?)
    """, (event_text, ws_id, full_prompt, response))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route("/")
def home():
    return "WonderSparks API is running."


@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    event_text = data.get("event")
    ws_id = int(data.get("ws_id"))

    sparks = load_wondersparks()
    if ws_id not in sparks:
        return jsonify({"error": "Invalid WonderSpark ID"}), 400

    ws = sparks[ws_id]
    full_prompt, ai_response = ask_wonder("Spark wonder in this event - keep it short.", ws['prompt'], event_text)
    save_reflection(event_text, ws_id, full_prompt, ai_response)

    return jsonify({
        "response": ai_response,
        "color": ws['color'],
        "lens_name": ws['name']
    })


@app.route("/reflections", methods=["GET"])
def reflections():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_text, ws_id, response FROM reflections ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {"event": r[0], "ws_id": r[1], "response": r[2]} for r in rows
    ])

# --- Run ---
if __name__ == "__main__":
    app.run(debug=True)
