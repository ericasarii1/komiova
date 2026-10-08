from flask import Flask, jsonify, request, send_from_directory
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static")

def load_comics():
    with open(os.path.join(BASE, "data", "comics.json"), encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/comics")
def api_comics():
    comics = load_comics()
    q = request.args.get("q", "").lower()
    if q:
        comics = [c for c in comics if q in c["title"].lower() or any(q in g.lower() for g in c["genre"])]
    return jsonify([{k: c[k] for k in ("id","title","author","genre","status","cover","desc")} for c in comics])

@app.route("/api/comics/<cid>")
def api_comic(cid):
    for c in load_comics():
        if c["id"] == cid:
            return jsonify(c)
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
