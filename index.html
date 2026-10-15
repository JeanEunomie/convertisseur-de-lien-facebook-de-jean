from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import html
from urllib.parse import urlparse, parse_qs, urlencode, unquote

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# =========================================================
# Vérifier qu'il s'agit bien d'un lien Facebook
# =========================================================

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


# =========================================================
# Nettoyer une URL Facebook
# =========================================================

def clean_facebook_url(url):

    p = urlparse(url)

    qs = parse_qs(p.query)

    path = unquote(
        p.path.rstrip("/") or "/"
    )


    # -----------------------------------------
    # CAS :
    # profile.php?id=123456
    # -----------------------------------------

    if path.lower() == "/profile.php":

        ids = qs.get("id")

        if ids and ids[0].isdigit():

            return (
                "https://www.facebook.com/"
                "profile.php?id="
                + ids[0]
            )


    # -----------------------------------------
    # Autres profils
    # -----------------------------------------

    keep = {}

    for key in (
        "id",
        "story_fbid",
        "fbid",
        "v"
    ):

        if qs.get(key):

            keep[key] = qs[key][0]


    result = (
        "https://www.facebook.com"
        + path
    )


    if keep:

        result += (
            "?"
            + urlencode(keep)
        )


    return result


# =========================================================
# Chercher un ID numérique Facebook dans la page
# =========================================================

def extract_numeric_id(text):

    if not text:

        return None


    text = html.unescape(text)


    patterns = [

        r'"userID"\s*:\s*"(\d{8,25})"',

        r'"user_id"\s*:\s*"(\d{8,25})"',

        r'"profile_id"\s*:\s*"(\d{8,25})"',

        r'profile\.php\?id=(\d{8,25})',

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )


        if match:

            return match.group(1)


    return None


# =========================================================
# Chercher un lien /people/.../pfbid...
# =========================================================

def extract_people_url(text):

    if not text:

        return None


    text = html.unescape(text)

    text = text.replace(
        "\\/",
        "/"
    )

    text = text.replace(
        "\\u0026",
        "&"
    )


    match = re.search(

        r'https?://(?:www\.)?facebook\.com'
        r'(/people/[^"\'<>\s]+/pfbid[a-zA-Z0-9]+)',

        text,

        re.I
    )


    if match:

        return clean_facebook_url(

            "https://www.facebook.com"
            + match.group(1)
        )


    return None


# =========================================================
# Résoudre le lien Facebook
# =========================================================

def resolve_facebook(original):

    session = requests.Session()

    session.headers.update(
        HEADERS
    )


    try:

        response = session.get(

            original,

            allow_redirects=True,

            timeout=15
        )


    except requests.RequestException:

        return {
            "success": False,
            "error":
                "Impossible de contacter Facebook."
        }


    # =====================================================
    # 1 - Chercher un ID numérique dans la page
    # =====================================================

    numeric_id = extract_numeric_id(
        response.text
    )


    if numeric_id:

        return {

            "success": True,

            "url":
                "https://www.facebook.com/"
                "profile.php?id="
                + numeric_id,

            "method":
                "numeric_id"
        }


    # =====================================================
    # 2 - Chercher un lien /people/
    # =====================================================

    people_url = extract_people_url(
        response.text
    )


    if people_url:

        return {

            "success": True,

            "url":
                people_url,

            "method":
                "people"
        }


    # =====================================================
    # 3 - Utiliser simplement la redirection Facebook
    # =====================================================

    final_url = response.url


    if is_facebook(final_url):

        return {

            "success": True,

            "url":
                clean_facebook_url(
                    final_url
                ),

            "method":
                "redirect"
        }


    return {

        "success": False,

        "error":
            "Impossible de retrouver le profil Facebook."
    }


# =========================================================
# Page principale
# =========================================================

@app.get("/")
def home():

    return send_from_directory(
        ".",
        "index.html"
    )


# =========================================================
# API
# =========================================================

@app.post("/api/resolve")
def resolve():

    data = (
        request.get_json(silent=True)
        or {}
    )


    original = (
        data.get("url", "")
        .strip()
    )


    if not is_facebook(original):

        return jsonify(

            success=False,

            error=
                "Colle un lien Facebook valide."

        ), 400


    result = resolve_facebook(
        original
    )


    if result.get("success"):

        return jsonify(

            success=True,

            final_url=
                result["url"],

            method=
                result.get("method")
        )


    return jsonify(

        success=False,

        error=
            result.get(
                "error",
                "Impossible de convertir ce lien."
            )

    ), 400


# =========================================================
# Lancement
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
