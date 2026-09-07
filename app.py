from flask import Flask, request, jsonify, send_from_directory
import requests, re, html
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, unquote

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
        path = p.path.rstrip("/") or "/"
        if path.lower() == "/profile.php" and qs.get("id"):
            fb_id = qs["id"][0]
            if fb_id.isdigit():
                return "https://www.facebook.com/profile.php?" + urlencode({"id": fb_id})
        keep = {}
        for key in ("id", "story_fbid", "fbid", "v"):
            if key in qs and qs[key]:
                keep[key] = qs[key][0]
        base = "https://www.facebook.com" + path
        return base + ("?" + urlencode(keep) if keep else "")
    except Exception:
        return url


def try_people_numeric(url):
    try:
        if not urlparse(url).path.lower().startswith("/people/"):
            return None
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"}, allow_redirects=True)
        fp, fq = urlparse(r.url), parse_qs(urlparse(r.url).query)
        if fp.path.rstrip("/").lower() == "/profile.php" and fq.get("id") and fq["id"][0].isdigit():
            return fq["id"][0]
        text = html.unescape(r.text)
        for pat in (r'"userID"\s*:\s*"(\d{8,25})"', r'"user_id"\s*:\s*"(\d{8,25})"',
                    r'"profile_id"\s*:\s*"(\d{8,25})"', r'profile\.php\?id=(\d{8,25})'):
            m = re.search(pat, text, re.I)
            if m: return m.group(1)
    except requests.RequestException:
        pass
    return None

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
        cleaned = clean_facebook_url(current)
        if urlparse(cleaned).path.lower().startswith("/people/"):
            fb_id = try_people_numeric(cleaned)
            if fb_id:
                cleaned = "https://www.facebook.com/profile.php?id=" + fb_id
        return jsonify(final_url=cleaned)
    except requests.RequestException:
        return jsonify(error="Facebook n'a pas permis de résoudre ce lien sans connexion."), 502
