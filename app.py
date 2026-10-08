from flask import Flask, jsonify, request, send_from_directory, Response
import json, os, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

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

_READABLE = {}

def readable_chapters(mid):
    """True if the manga has at least one internal (viewable) id/en chapter."""
    if mid in _READABLE:
        return _READABLE[mid]
    try:
        ch = md_get("/manga/%s/feed" % mid, {
            "translatedLanguage[]": ["id", "en"], "limit": 1,
            "order[chapter]": "asc", "includeExternalUrl": 0,
        })
        ok = ch.get("total", 0) > 0
    except Exception:
        ok = False
    _READABLE[mid] = ok
    return ok


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
    titles = m["attributes"].get("title", {}) or {}
    title = titles.get("id") or titles.get("en") or next(iter(titles.values()), "Untitled")
    descs = m["attributes"].get("description", {}) or {}
    desc = descs.get("id") or descs.get("en") or ""
    tags = [t["attributes"]["name"].get("id") or t["attributes"]["name"].get("en", "")
            for t in m["attributes"].get("tags", [])]
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
    base = {
        "limit": 60, "contentRating[]": ["safe", "suggestive"],
        "includes[]": ["cover_art", "author"],
        "hasAvailableChapters": "true",
    }
    params = {**base, "order[relevance]" if q else "order[followedCount]": "desc"}
    if q:
        params["title"] = q
    data = md_get("/manga", params)
    candidates = data.get("data", [])
    with ThreadPoolExecutor(max_workers=10) as ex:
        flags = list(ex.map(lambda m: readable_chapters(m["id"]), candidates))
    readable = [m for m, ok in zip(candidates, flags) if ok][:24]
    return jsonify([parse_manga(m, None) for m in readable])

@app.route("/api/manga/<mid>")
def api_manga_detail(mid):
    data = md_get(f"/manga/{mid}", {"includes[]": ["cover_art", "author"]})
    info = parse_manga(data["data"], None)
    # chapters: prefer Indonesian, fallback to English
    ch = md_get("/manga/%s/feed" % mid, {
        "translatedLanguage[]": ["id", "en"], "limit": 500, "order[chapter]": "asc",
        "includeExternalUrl": 0,
    })
    lang_used = "id"
    chapters = []
    for c in ch.get("data", []):
        a = c["attributes"]
        if a.get("externalUrl"): continue
        chapters.append({
            "id": c["id"],
            "num": a.get("chapter") or "0",
            "title": a.get("title") or "Chapter " + str(a.get("chapter") or ""),
            "pages_count": a.get("pages", 0),
            "lang": a.get("translatedLanguage", "en"),
        })
    info["chapter_lang"] = "id+en"
    def _ch_key(c):
        try:
            return float(c["num"])
        except (TypeError, ValueError):
            return float("inf")
    info["chapters"] = sorted(chapters, key=_ch_key)
    return jsonify(info)

@app.route("/api/updates")
def api_updates():
    """Bulk: for up to 60 manga ids, return the newest chapter (num + id + lang)."""
    ids = [i for i in request.args.get("ids", "").split(",") if i][:60]
    if not ids:
        return jsonify({})

    def latest(mid):
        try:
            ch = md_get("/manga/%s/feed" % mid, {
                "translatedLanguage[]": ["id", "en"], "limit": 1,
                "order[chapter]": "desc", "includeExternalUrl": 0,
            })
            data = ch.get("data", [])
            if not data:
                return mid, None
            a = data[0]["attributes"]
            return mid, {
                "id": data[0]["id"], "num": a.get("chapter") or "0",
                "title": a.get("title") or "", "lang": a.get("translatedLanguage", "en"),
                "published": a.get("publishAt", ""),
            }
        except Exception:
            return mid, None

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = dict(ex.map(latest, ids))
    return jsonify(results)


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
