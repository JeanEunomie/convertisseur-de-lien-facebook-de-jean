from flask import Flask, request, jsonify, send_from_directory
import requests, re, html
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, unquote

application = Flask(__nom__)

def facebook_url(url):
    essayer:
        p = urlparse(url)
        h = (p.hostname ou "").lower()
        retourner p.scheme dans ("http", "https") et (h == "facebook.com" ou h.endswith(".facebook.com") ou h == "fb.com" ou h.endswith(".fb.com"))
    sauf exception :
        renvoyer Faux

def clean_facebook_url(url):
    essayer:
        p = urlparse(url)
        qs = parse_qs(p.query)
        chemin = p.path.rstrip("/") ou "/"
        si path.lower() == "/profile.php" et qs.get("id"):
            fb_id = qs["id"][0]
            si fb_id.isdigit():
                renvoie "https://www.facebook.com/profile.php?" + urlencode({"id": fb_id})
        garder = {}
        pour chaque clé dans ("id", "story_fbid", "fbid", "v") :
            si la clé est dans qs et qs[clé] :
                garder[clé] = qs[clé][0]
        base = "https://www.facebook.com" + chemin
        renvoyer la base + ("?" + urlencode(keep) si conserver sinon "")
    sauf exception :
        URL de retour


def essayer_personnes_numérique(url):
    essayer:
        si urlparse(url).path.lower().startswith("/people/") :
            renvoyer Aucun
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"}, allow_redirects=True)
        fp, fq = urlparse(r.url), parse_qs(urlparse(r.url).query)
        si fp.path.rstrip("/").lower() == "/profile.php" et fq.get("id") et fq["id"][0].isdigit():
            renvoyer fq["id"][0]
        texte = html.unescape(r.text)
        pour pat dans (r'"userID"\s*:\s*"(\d{8,25})"', r'"user_id"\s*:\s*"(\d{8,25})"',
                    r'"profile_id"\s*:\s*"(\d{8,25})"', r'profile\.php\?id=(\d{8,25})'):
            m = re.search(pat, text, re.I)
            si m : retourner m.groupe(1)
    sauf requests.RequestException :
        passer
    renvoyer Aucun

@app.get("/")
def index():
    renvoyer send_from_directory(".", "index.html")

@app.post("/api/resolve")
def resolve():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    si facebook_url(url) n'est pas :
        return jsonify(error="Colle un lien Facebook valide."), 400
    essayer:
        actuel = url
        pour _ dans la plage(10) :
            r = requests.get(current, allow_redirects=False, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            si r.is_redirect ou r.is_permanent_redirect :
                nxt = urljoin(current, r.headers.get("Location", ""))
                si ce n'est pas facebook_url(nxt) :
                    return jsonify(error="La redirection quitte Facebook."), 400
                courant = nxt
            autre:
                casser
        nettoyé = clean_facebook_url(actuel)
        si urlparse(cleaned).path.lower().startswith("/people/"):
            fb_id = essayer_personnes_numérique(nettoyé)
            si fb_id :
                nettoyé = "https://www.facebook.com/profile.php?id=" + fb_id
        retourner jsonify(final_url=nettoyé)
    sauf requests.RequestException :
        return jsonify(error="Facebook n'a pas permis de résoudre ce lien sans connexion."), 502
