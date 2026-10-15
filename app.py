from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import html
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, unquote

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 "
        "Chrome/124.0 Mobile Safari/537.36"
    )
}


def facebook_url(url):
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()

        return (
            p.scheme in ("http", "https")
            and (
                host == "facebook.com"
                or host.endswith(".facebook.com")
                or host == "fb.com"
                or host.endswith(".fb.com")
            )
        )
    except Exception:
        return False


def is_login_url(url):
    try:
        path = urlparse(url).path.lower()

        return (
            path == "/login"
            or path.startswith("/login/")
            or path == "/login.php"
        )
    except Exception:
        return False


def extract_next(url):
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if "next" not in params:
            return None

        next_url = unquote(params["next"][0])

        if facebook_url(next_url):
            return next_url

    except Exception:
        pass

    return None


def clean_facebook_url(url):
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)

        path = p.path.rstrip("/") or "/"

        # Profil avec ID numérique
        if path.lower() == "/profile.php" and qs.get("id"):

            fb_id = qs["id"][0]

            if fb_id.isdigit():
                return (
                    "https://www.facebook.com/"
                    "profile.php?id=" + fb_id
                )

        # Paramètres utiles uniquement
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


def find_numeric_id(text):
    if not text:
        return None

    text = html.unescape(text)

    patterns = [
        r'"userID"\s*:\s*"(\d{8,25})"',
        r'"user_id"\s*:\s*"(\d{8,25})"',
        r'"profile_id"\s*:\s*"(\d{8,25})"',
        r'"actorID"\s*:\s*"(\d{8,25})"',
        r'profile\.php\?id=(\d{8,25})'
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None


def try_people_numeric(url):
    try:
        path = urlparse(url).path.lower()

        if not path.startswith("/people/"):
            return None

        response = requests.get(
            url,
            timeout=12,
            allow_redirects=True,
            headers=HEADERS
        )

        final_url = response.url

        p = urlparse(final_url)
        qs = parse_qs(p.query)

        # Facebook redirige directement vers profile.php?id=
        if (
            p.path.rstrip("/").lower() == "/profile.php"
            and qs.get("id")
        ):
            fb_id = qs["id"][0]

            if fb_id.isdigit():
                return fb_id

        # Recherche dans la page
        return find_numeric_id(response.text)

    except requests.RequestException:
        return None


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.post("/api/resolve")
def resolve():

    data = request.get_json(silent=True) or {}

    original_url = data.get("url", "").strip()

    if not facebook_url(original_url):
        return jsonify(
            error="Colle un lien Facebook valide."
        ), 400

    try:

        current = original_url

        for _ in range(12):

            response = requests.get(
                current,
                allow_redirects=False,
                timeout=12,
                headers=HEADERS
            )

            if not (
                response.is_redirect
                or response.is_permanent_redirect
            ):
                break

            location = response.headers.get("Location")

            if not location:
                break

            next_url = urljoin(current, location)

            if not facebook_url(next_url):
                return jsonify(
                    error="La redirection quitte Facebook."
                ), 400

            # Facebook demande une connexion
            if is_login_url(next_url):

                destination = extract_next(next_url)

                # Si "next" contient déjà une vraie destination
                if (
                    destination
                    and destination != original_url
                    and "/share/" not in
                    urlparse(destination).path.lower()
                ):
                    current = destination
                    break

                # Cas LOGIN :
                # on renvoie le lien original au navigateur
                return jsonify(
                    status="login_required",
                    message=(
                        "Facebook demande une connexion "
                        "pour terminer la conversion."
                    ),
                    browser_url=original_url
                ), 200

            current = next_url


        # Sécurité supplémentaire
        if is_login_url(current):

            return jsonify(
                status="login_required",
                message=(
                    "Facebook demande une connexion "
                    "pour terminer la conversion."
                ),
                browser_url=original_url
            ), 200


        cleaned = clean_facebook_url(current)


        # Facebook n'a toujours pas résolu /share/
        if "/share/" in urlparse(cleaned).path.lower():

            return jsonify(
                status="login_required",
                message=(
                    "Facebook doit ouvrir ce lien "
                    "dans ton navigateur pour continuer."
                ),
                browser_url=original_url
            ), 200


        # Tentative de conversion /people/ vers ID numérique
        if (
            urlparse(cleaned)
            .path
            .lower()
            .startswith("/people/")
        ):

            fb_id = try_people_numeric(cleaned)

            if fb_id:
                cleaned = (
                    "https://www.facebook.com/"
                    "profile.php?id=" + fb_id
                )


        return jsonify(
            status="success",
            final_url=cleaned
        )


    except requests.RequestException:

        return jsonify(
            error=(
                "Facebook n'a pas permis "
                "de résoudre ce lien."
            )
        ), 502
