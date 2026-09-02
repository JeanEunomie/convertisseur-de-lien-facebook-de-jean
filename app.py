from flask import Flask, request, jsonify, send_from_directory
import requests
from urllib.parse import urlparse, urljoin, parse_qs, urlencode

app = Flask(__name__)

def facebook_url(url):
    try:
        p = urlparse(url)
        h = (p.hostname or "").lower()
        return p.scheme in ("http", "https") and (h == "facebook.com" or h.endswith(".facebook.com") or h == "fb.com" or h.endswith(".fb.com"))
    except Exception:
        return False

def clean_facebook_url(url):
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)
        if p.path.rstrip("/").lower() == "/profile.php" and qs.get("id"):
            fb_id = qs["id"][0]
            if fb_id.isdigit():
                return "https://www.facebook.com/profile.php?" + urlencode({"id": fb_id})
        return url
    except Exception:
        return url

@app.get("/")
def index():
    return send_from_directory(".", "index.html")

@app.post("/api/resolve")
def resolve():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not facebook_url(url):
        return jsonify(error="Colle un lien Facebook valide."), 400
    try:
        current = url
        for _ in range(10):
            r = requests.get(current, allow_redirects=False, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if r.is_redirect or r.is_permanent_redirect:
                nxt = urljoin(current, r.headers.get("Location", ""))
                if not facebook_url(nxt):
                    return jsonify(error="La redirection quitte Facebook."), 400
                current = nxt
            else:
                break
        return jsonify(final_url=clean_facebook_url(current))
    except requests.RequestException:
        return jsonify(error="Facebook n'a pas permis de résoudre ce lien sans connexion."), 502
