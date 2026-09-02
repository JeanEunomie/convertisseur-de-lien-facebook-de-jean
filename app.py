from flask import Flask, request, jsonify, send_from_directory
import requests
from urllib.parse import urlparse, urljoin

app = Flask(__name__, static_folder="static")

def facebook_url(url):
    try:
        p = urlparse(url)
        h = (p.hostname or "").lower()
        return p.scheme in ("http","https") and (
            h == "facebook.com" or h.endswith(".facebook.com") or
            h == "fb.com" or h.endswith(".fb.com")
        )
    except Exception:
        return False

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.post("/api/resolve")
def resolve():
    url = (request.get_json(silent=True) or {}).get("url","").strip()
    if not facebook_url(url):
        return jsonify(error="Colle un lien Facebook valide."), 400
    try:
        current = url
        for _ in range(10):
            r = requests.get(current, allow_redirects=False, timeout=12,
                headers={"User-Agent":"Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
            if r.is_redirect or r.is_permanent_redirect:
                nxt = urljoin(current, r.headers.get("Location",""))
                if not facebook_url(nxt):
                    return jsonify(error="La redirection quitte Facebook."), 400
                current = nxt
            else:
                break
        return jsonify(final_url=current)
    except requests.RequestException:
        return jsonify(error="Facebook n'a pas permis de résoudre ce lien sans connexion."), 502
