from flask import Flask, jsonify, request, send_from_directory, Response
import json, os, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static")

MD = "https://api.mangadex.org"
UA = "KomiOva/1.0"

def md_get(path, params=None):
    url = MD + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def img_proxy(url):
    return "/api/image?u=" + urllib.parse.quote(url, safe="")

@app.route("/api/image")
def api_image():
    u = request.args.get("u", "")
    host = urllib.parse.urlparse(u).hostname or ""
    if not (host == "uploads.mangadex.org" or host.endswith(".mangadex.network")
            or host.endswith(".mangadex.org")):
        return jsonify({"error": "bad url"}), 400
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    return Response(data, content_type=ct)

def parse_manga(m, cover_art=None):
    rels = m.get("relationships", [])
    fname = next((r["attributes"]["fileName"] for r in rels
                  if r["type"] == "cover_art" and r.get("attributes")), None)
    cover = (f"https://uploads.mangadex.org/covers/{m['id']}/{fname}.256.jpg"
             if fname else "")
    title = (m["attributes"].get("title", {}).get("en")
             or next(iter(m["attributes"].get("title", {}).values()), "Untitled"))
    desc = m["attributes"].get("description", {}).get("en") or ""
    tags = [t["attributes"]["name"].get("en", "") for t in m["attributes"].get("tags", [])]
    author = next((r["attributes"]["name"] for r in rels
                   if r["type"] == "author" and r.get("attributes")
                   and r["attributes"].get("name")), "-")
    return {
        "id": m["id"], "title": title,
        "author": author,
        "status": (m["attributes"].get("status") or "unknown").capitalize(),
        "desc": desc[:500], "tags": tags, "cover": img_proxy(cover),
    }

@app.route("/api/manga")
def api_manga():
    q = request.args.get("q", "")
    params = {
        "limit": 24, "order[followedCount]": "desc",
        "contentRating[]": ["safe", "suggestive"],
        "includes[]": ["cover_art", "author"],
    }
    if q:
        params = {"limit": 24, "title": q, "contentRating[]": ["safe", "suggestive"], "includes[]": ["cover_art", "author"], "order[relevance]": "desc"}
    data = md_get("/manga", params)
    return jsonify([parse_manga(m, None) for m in data.get("data", [])])

@app.route("/api/manga/<mid>")
def api_manga_detail(mid):
    data = md_get(f"/manga/{mid}", {"includes[]": ["cover_art", "author"]})
    info = parse_manga(data["data"], None)
    # chapters
    ch = md_get("/manga/%s/feed" % mid, {
        "translatedLanguage[]": ["en"], "limit": 100, "order[chapter]": "desc",
        "contentRating[]": ["safe", "suggestive"],
        "includeExternalUrl": 0,
    })
    chapters = []
    for c in ch.get("data", []):
        a = c["attributes"]
        if a.get("externalUrl"): continue
        chapters.append({
            "id": c["id"],
            "num": a.get("chapter") or "0",
            "title": a.get("title") or "Chapter " + str(a.get("chapter") or ""),
            "pages_count": a.get("pages", 0),
        })
    info["chapters"] = chapters
    return jsonify(info)

@app.route("/api/chapter/<cid>")
def api_chapter(cid):
    d = md_get(f"/at-home/server/{cid}")
    base, chapter = d.get("baseUrl"), d.get("chapter", {})
    h = chapter.get("hash", "")
    pages = [img_proxy(f"{base}/data/{h}/{p}") for p in chapter.get("data", [])]
    return jsonify({"pages": pages})

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
