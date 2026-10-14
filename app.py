from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import html
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, unquote

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

def is_facebook(url):
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


def path_of(url):
    try:
        return unquote(urlparse(url).path or "/")
    except Exception:
        return "/"


def is_login(url):
    return path_of(url).lower().startswith("/login")


def is_share(url):
    path = path_of(url).lower()
    return (
        path.startswith("/share/")
        or path.startswith("/share.php")
        or path.startswith("/sharer/")
        or path.startswith("/sharer.php")
    )


def clean_facebook_url(url):
    """
    Nettoie un lien Facebook déjà identifié.
    Ne prétend pas résoudre un /share/.
    """

    p = urlparse(url)
    qs = parse_qs(p.query)

    path = unquote(p.path.rstrip("/") or "/")

    # Profil avec ID numérique
    if path.lower() == "/profile.php":
        ids = qs.get("id")

        if ids and ids[0].isdigit():
            return (
                "https://www.facebook.com/profile.php?"
                + urlencode({"id": ids[0]})
            )

    # Pour certains types de liens Facebook où un paramètre
    # fait réellement partie de l'adresse.
    keep = {}

    for key in ("id", "story_fbid", "fbid", "v"):
        if qs.get(key):
            keep[key] = qs[key][0]

    result = "https://www.facebook.com" + path

    if keep:
        result += "?" + urlencode(keep)

    return result


def extract_numeric_id(text):
    """
    Cherche uniquement des identifiants explicitement présents.
    Aucun ID n'est inventé ou calculé.
    """

    if not text:
        return None

    text = html.unescape(text)

    patterns = [
        r'"userID"\s*:\s*"(\d{8,25})"',
        r'"user_id"\s*:\s*"(\d{8,25})"',
        r'"profile_id"\s*:\s*"(\d{8,25})"',
        r'"actorID"\s*:\s*"(\d{8,25})"',
        r'"owner_id"\s*:\s*"(\d{8,25})"',
        r'profile\.php\?id=(\d{8,25})',
        r'profile_id=(\d{8,25})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            return match.group(1)

    return None


def extract_profile_url(text):
    """
    Cherche dans le HTML un vrai lien de profil Facebook.
    """

    if not text:
        return None

    text = html.unescape(text)
    text = text.replace("\\/", "/")
    text = text.replace("\\u0026", "&")

    # profile.php?id=...
    match = re.search(
        r'https?://(?:www\.)?facebook\.com/profile\.php\?id=(\d{8,25})',
        text,
        re.I
    )

    if match:
        return (
            "https://www.facebook.com/profile.php?id="
            + match.group(1)
        )

    # /people/Nom/pfbid...
    match = re.search(
        r'https?://(?:www\.)?facebook\.com'
        r'(/people/[^"\'<>\s]+/pfbid[a-zA-Z0-9]+)',
        text,
        re.I
    )

    if match:
        return clean_facebook_url(
            "https://www.facebook.com" + match.group(1)
        )

    return None


def resolve_facebook(original):
    """
    Suit les redirections Facebook et essaie plusieurs méthodes.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    current = original
    visited = []

    for _ in range(12):

        visited.append(current)

        try:
            r = session.get(
                current,
                allow_redirects=False,
                timeout=15
            )
        except requests.RequestException:
            return {
                "success": False,
                "reason": "network"
            }

        # Chercher un ID dans la page reçue
        numeric_id = extract_numeric_id(r.text)

        if numeric_id:
            return {
                "success": True,
                "url": (
                    "https://www.facebook.com/profile.php?id="
                    + numeric_id
                ),
                "method": "numeric_id"
            }

        # Chercher un vrai lien de profil dans le HTML
        profile_url = extract_profile_url(r.text)

        if profile_url and not is_share(profile_url):
            return {
                "success": True,
                "url": profile_url,
                "method": "html_profile"
            }

        # Redirection HTTP
        if r.is_redirect or r.is_permanent_redirect:

            location = r.headers.get("Location")

            if not location:
                break

            nxt = urljoin(current, location)

            if not is_facebook(nxt):
                break

            # Facebook demande une connexion
            if is_login(nxt):
                return {
                    "success": False,
                    "reason": "login",
                    "last_url": current
                }

            current = nxt
            continue

        break

    # Si la destination est un vrai profil
    if (
        is_facebook(current)
        and not is_login(current)
        and not is_share(current)
    ):
        return {
            "success": True,
            "url": clean_facebook_url(current),
            "method": "redirect"
        }

    # IMPORTANT :
    # on ne considère jamais /share/... comme un résultat final.
    return {
        "success": False,
        "reason": "unresolved",
        "last_url": current
    }


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


@app.post("/api/resolve")
def resolve():

    data = request.get_json(silent=True) or {}
    original = data.get("url", "").strip()

    if not is_facebook(original):
        return jsonify(
            success=False,
            error="Colle un lien Facebook valide."
        ), 400

    result = resolve_facebook(original)

    if result.get("success"):
        return jsonify(
            success=True,
            final_url=result["url"],
            method=result.get("method")
        )

    reason = result.get("reason")

    if reason == "login":
        message = (
            "Facebook demande une connexion et empêche "
            "le serveur d'identifier automatiquement ce profil."
        )

    elif reason == "network":
        message = (
            "Impossible de contacter Facebook correctement. "
            "Réessaie dans quelques instants."
        )

    else:
        message = (
            "Facebook n'a pas fourni suffisamment d'informations "
            "pour retrouver automatiquement le lien permanent."
        )

    return jsonify(
        success=False,
        blocked=True,
        reason=reason,
        message=message,
        original_url=original
    )


@app.post("/api/clean")
def manual_clean():

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    if not is_facebook(url):
        return jsonify(
            success=False,
            error="Colle un lien Facebook valide."
        ), 400

    if is_login(url):
        return jsonify(
            success=False,
            error="Ce lien correspond à la page de connexion Facebook."
        ), 400

    # Si l'utilisateur remet un /share/,
    # on tente à nouveau de le résoudre.
    if is_share(url):

        result = resolve_facebook(url)

        if result.get("success"):
            return jsonify(
                success=True,
                final_url=result["url"]
            )

        return jsonify(
            success=False,
            blocked=True,
            message=(
                "Facebook a encore fourni un lien /share/. "
                "Ce lien ne peut pas être transformé de façon fiable "
                "sans que Facebook révèle le profil correspondant."
            )
        )

    return jsonify(
        success=True,
        final_url=clean_facebook_url(url)
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
