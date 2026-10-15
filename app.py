from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import html
from urllib.parse import urlparse, urljoin, parse_qs, urlencode

app = Flask(__name__)


def facebook_url(url):
    try:
        p = urlparse(url)
        h = (p.hostname or "").lower()

        return p.scheme in ("http", "https") and (
            h == "facebook.com"
            or h.endswith(".facebook.com")
            or h == "fb.com"
            or h.endswith(".fb.com")
        )
    except Exception:
        return False


def clean_facebook_url(url):
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)

        path = p.path.rstrip("/") or "/"

        # Cas profile.php?id=123456...
        if path.lower() == "/profile.php" and qs.get("id"):
            fb_id = qs["id"][0]

            if fb_id.isdigit():
                return (
                    "https://www.facebook.com/profile.php?id="
                    + fb_id
                )

        # Paramètres utiles à conserver
        keep = {}

        for key in ("id", "story_fbid", "fbid", "v"):
            if key in qs and qs[key]:
                keep[key] = qs[key][0]

        base = "https://www.facebook.com" + path

        if keep:
            return base + "?" + urlencode(keep)

        return base

    except Exception:
        return url


def try_people_numeric(url):

    try:
        p = urlparse(url)

        # On ne fait cette recherche que pour /people/
        if not p.path.lower().startswith("/people/"):
            return None

        r = requests.get(
            url,
            timeout=12,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        # Vérifie si Facebook redirige vers profile.php?id=
        final_url = r.url
        fp = urlparse(final_url)
        fqs = parse_qs(fp.query)

        if (
            fp.path.rstrip("/").lower() == "/profile.php"
            and fqs.get("id")
        ):
            fb_id = fqs["id"][0]

            if fb_id.isdigit():
                return fb_id

        # Sinon on cherche l'ID dans le contenu Facebook
        page = html.unescape(r.text)

        patterns = [
            r'"userID"\s*:\s*"(\d{8,25})"',
            r'"user_id"\s*:\s*"(\d{8,25})"',
            r'"profile_id"\s*:\s*"(\d{8,25})"',
            r'profile\.php\?id=(\d{8,25})'
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                page,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

    except requests.RequestException:
        pass

    return None


@app.get("/")
def index():

    return send_from_directory(
        ".",
        "index.html"
    )


@app.post("/api/resolve")
def resolve():

    url = (
        request.get_json(silent=True) or {}
    ).get("url", "").strip()

    if not facebook_url(url):

        return jsonify(
            error="Colle un lien Facebook valide."
        ), 400

    try:

        current = url

        # Suit les redirections Facebook
        for _ in range(10):

            r = requests.get(
                current,
                allow_redirects=False,
                timeout=12,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            if r.is_redirect or r.is_permanent_redirect:

                nxt = urljoin(
                    current,
                    r.headers.get("Location", "")
                )

                if not facebook_url(nxt):

                    return jsonify(
                        error="La redirection quitte Facebook."
                    ), 400

                current = nxt

            else:
                break

        # Nettoyage du lien obtenu
        cleaned = clean_facebook_url(current)

        # Si Facebook donne /people/Nom/pfbid...
        # on tente de retrouver l'ID numérique
        if urlparse(cleaned).path.lower().startswith("/people/"):

            fb_id = try_people_numeric(cleaned)

            if fb_id:

                cleaned = (
                    "https://www.facebook.com/"
                    "profile.php?id="
                    + fb_id
                )

        return jsonify(
            final_url=cleaned
        )

    except requests.RequestException:

        return jsonify(
            error="Facebook n'a pas permis de résoudre ce lien."
        ), 502
