from flask import Flask, request, jsonify, send_from_directory
import requests
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, unquote

app = Flask(__name__)

def is_facebook(url):
    try:
        p = urlparse(url)
        h = (p.hostname or "").lower()
        return p.scheme in ("http", "https") and (
            h == "facebook.com" or h.endswith(".facebook.com") or
            h == "fb.com" or h.endswith(".fb.com")
        )
    except Exception:
        return False

def clean(url):
    p = urlparse(url)
    qs = parse_qs(p.query)
    path = unquote(p.path.rstrip("/") or "/")
    if path.lower() == "/profile.php" and qs.get("id") and qs["id"][0].isdigit():
        return "https://www.facebook.com/profile.php?" + urlencode({"id": qs["id"][0]})
    keep = {}
    for k in ("id", "story_fbid", "fbid", "v"):
        if qs.get(k):
            keep[k] = qs[k][0]
    return "https://www.facebook.com" + path + (("?" + urlencode(keep)) if keep else "")

@app.get("/")
def home():
    return send_from_directory(".", "index.html")

@app.post("/api/resolve")
def resolve():
    original = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not is_facebook(original):
        return jsonify(error="Colle un lien Facebook valide."), 400
    try:
        current = original
        for _ in range(10):
            r = requests.get(current, allow_redirects=False, timeout=12,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.is_redirect or r.is_permanent_redirect:
                nxt = urljoin(current, r.headers.get("Location", ""))
                if not is_facebook(nxt):
                    break
                current = nxt
            else:
                break
        if urlparse(current).path.lower().startswith("/login"):
            return jsonify(blocked=True, original_url=original)
        return jsonify(blocked=False, final_url=clean(current))
    except requests.RequestException:
        return jsonify(blocked=True, original_url=original)

@app.post("/api/clean")
def manual_clean():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not is_facebook(url):
        return jsonify(error="Colle un lien Facebook valide."), 400
    if urlparse(url).path.lower().startswith("/login"):
        return jsonify(error="Ce lien est encore la page de connexion Facebook."), 400
    return jsonify(final_url=clean(url))
