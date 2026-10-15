from flask import Flask, request, jsonify, send_from_directory
import requests
import re
import html
from urllib.parse import (
    urlparse,
    urljoin,
    parse_qs,
    urlencode,
    unquote
)

app = Flask(__name__)

# Plusieurs User-Agent.
# Facebook peut répondre différemment selon le navigateur présenté.
USER_AGENTS = [
    (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
]


# ==========================================================
# VÉRIFICATIONS
# ==========================================================

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


def get_path(url):
    try:
        return unquote(
            urlparse(url).path or "/"
        )
    except Exception:
        return "/"


def is_login(url):
    return get_path(url).lower().startswith(
        "/login"
    )


def is_share(url):
    path = get_path(url).lower()

    return (
        path.startswith("/share/")
        or path.startswith("/share.php")
        or path.startswith("/sharer/")
        or path.startswith("/sharer.php")
    )


def is_home(url):
    try:
        path = get_path(url).rstrip("/")

        return path == ""

    except Exception:
        return False


# ==========================================================
# NETTOYAGE
# ==========================================================

def clean_facebook_url(url):

    p = urlparse(url)

    qs = parse_qs(p.query)

    path = unquote(
        p.path.rstrip("/") or "/"
    )


    # ------------------------------------------
    # profile.php?id=123456
    # ------------------------------------------

    if path.lower() == "/profile.php":

        ids = qs.get("id")

        if (
            ids
            and ids[0].isdigit()
        ):

            return (
                "https://www.facebook.com/"
                "profile.php?id="
                + ids[0]
            )


    # ------------------------------------------
    # Autres liens Facebook
    # ------------------------------------------

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


# ==========================================================
# EST-CE UN VRAI RÉSULTAT ?
# ==========================================================

def valid_final_url(url):

    if not is_facebook(url):
        return False

    if is_login(url):
        return False

    if is_share(url):
        return False

    if is_home(url):
        return False

    path = get_path(url).lower()

    # Pages techniques Facebook
    blocked_paths = (
        "/checkpoint",
        "/recover",
        "/help",
        "/privacy",
        "/policies",
        "/cookie",
    )

    for blocked in blocked_paths:

        if path.startswith(blocked):
            return False

    return True


# ==========================================================
# EXTRACTION D'UN ID NUMÉRIQUE
# ==========================================================

def extract_numeric_id(text):

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

        r'profile_id=(\d{8,25})'
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


# ==========================================================
# EXTRACTION D'UN LIEN DE PROFIL
# ==========================================================

def extract_profile_url(text):

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


    # ------------------------------------------
    # profile.php?id=
    # ------------------------------------------

    match = re.search(
        r'https?://(?:www\.|m\.)?facebook\.com/'
        r'profile\.php\?id=(\d{8,25})',
        text,
        re.I
    )


    if match:

        return (
            "https://www.facebook.com/"
            "profile.php?id="
            + match.group(1)
        )


    # ------------------------------------------
    # /people/.../pfbid...
    # ------------------------------------------

    match = re.search(
        r'https?://(?:www\.|m\.)?facebook\.com'
        r'(/people/[^"\'<>\s]+/pfbid[a-zA-Z0-9]+)',
        text,
        re.I
    )


    if match:

        candidate = (
            "https://www.facebook.com"
            + match.group(1)
        )

        if valid_final_url(candidate):

            return clean_facebook_url(
                candidate
            )


    return None


# ==========================================================
# MÉTHODE 1 :
# REDIRECTIONS FACEBOOK
#
# C'est volontairement la première méthode.
# ==========================================================

def follow_redirects(original, user_agent):

    session = requests.Session()

    session.headers.update({
        "User-Agent": user_agent,
        "Accept-Language":
            "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept":
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
    })


    current = original


    for _ in range(12):

        try:

            response = session.get(
                current,
                allow_redirects=False,
                timeout=12
            )

        except requests.RequestException:

            return {
                "success": False,
                "reason": "network"
            }


        # --------------------------------------
        # 1. Vérification du HTML reçu
        # --------------------------------------

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


        profile_url = extract_profile_url(
            response.text
        )


        if (
            profile_url
            and valid_final_url(profile_url)
        ):

            return {
                "success": True,
                "url": profile_url,
                "method": "html"
            }


        # --------------------------------------
        # 2. REDIRECTION HTTP
        # --------------------------------------

        if (
            response.is_redirect
            or response.is_permanent_redirect
        ):

            location = response.headers.get(
                "Location"
            )


            if not location:
                break


            nxt = urljoin(
                current,
                location
            )


            if not is_facebook(nxt):
                break


            # IMPORTANT :
            # si la redirection donne directement
            # un vrai profil, on le prend.
            if valid_final_url(nxt):

                return {
                    "success": True,
                    "url":
                        clean_facebook_url(nxt),
                    "method":
                        "redirect"
                }


            # Facebook demande une connexion
            if is_login(nxt):

                return {
                    "success": False,
                    "reason": "login"
                }


            # Si Facebook redirige vers un autre
            # /share/, on continue au lieu de
            # l'afficher comme résultat.
            current = nxt

            continue


        # --------------------------------------
        # 3. URL finale de la requête
        # --------------------------------------

        final_response_url = response.url


        if valid_final_url(
            final_response_url
        ):

            return {
                "success": True,

                "url":
                    clean_facebook_url(
                        final_response_url
                    ),

                "method":
                    "response_url"
            }


        break


    return {
        "success": False,
        "reason": "unresolved"
    }


# ==========================================================
# RÉSOLUTION COMPLÈTE
# ==========================================================

def resolve_facebook(original):

    reasons = []


    # On essaie plusieurs présentations navigateur.
    for user_agent in USER_AGENTS:

        result = follow_redirects(
            original,
            user_agent
        )


        if result.get("success"):

            return result


        reasons.append(
            result.get("reason")
        )


    # Si au moins une tentative a été bloquée
    # par Facebook Login :
    if "login" in reasons:

        return {
            "success": False,
            "reason": "login"
        }


    if reasons and all(
        reason == "network"
        for reason in reasons
    ):

        return {
            "success": False,
            "reason": "network"
        }


    return {
        "success": False,
        "reason": "unresolved"
    }


# ==========================================================
# PAGE PRINCIPALE
# ==========================================================

@app.get("/")
def home():

    return send_from_directory(
        ".",
        "index.html"
    )


# ==========================================================
# API CONVERSION
# ==========================================================

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


    # ------------------------------------------
    # Si l'utilisateur donne déjà un vrai lien
    # Facebook, pas besoin de résolution.
    # ------------------------------------------

    if (
        valid_final_url(original)
        and not is_share(original)
    ):

        return jsonify(
            success=True,
            final_url=
                clean_facebook_url(original),
            method="already_valid"
        )


    # ------------------------------------------
    # Résolution
    # ------------------------------------------

    result = resolve_facebook(
        original
    )


    if result.get("success"):

        return jsonify(
            success=True,
            final_url=result["url"],
            method=result.get("method")
        )


    reason = result.get(
        "reason"
    )


    if reason == "login":

        message = (
            "Facebook demande une connexion "
            "et empêche le serveur d'identifier "
            "automatiquement ce profil."
        )


    elif reason == "network":

        message = (
            "Impossible de contacter Facebook "
            "correctement. Réessaie dans "
            "quelques instants."
        )


    else:

        message = (
            "Facebook n'a pas fourni suffisamment "
            "d'informations pour retrouver "
            "automatiquement le lien permanent."
        )


    return jsonify(
        success=False,
        blocked=True,
        reason=reason,
        message=message,
        original_url=original
    )


# ==========================================================
# API ANALYSE MANUELLE
# ==========================================================

@app.post("/api/clean")
def manual_clean():

    data = (
        request.get_json(silent=True)
        or {}
    )

    url = (
        data.get("url", "")
        .strip()
    )


    if not is_facebook(url):

        return jsonify(
            success=False,
            error=
                "Colle un lien Facebook valide."
        ), 400


    if is_login(url):

        return jsonify(
            success=False,
            error=
                "Ce lien correspond à la page "
                "de connexion Facebook."
        ), 400


    # ------------------------------------------
    # Encore un /share/
    #
    # On tente réellement de le résoudre.
    # ------------------------------------------

    if is_share(url):

        result = resolve_facebook(
            url
        )


        if result.get("success"):

            return jsonify(
                success=True,
                final_url=result["url"]
            )


        return jsonify(
            success=False,
            blocked=True,

            message=(
                "Facebook a encore fourni un lien "
                "/share/. Le profil correspondant "
                "n'est pas accessible au serveur."
            )
        )


    # ------------------------------------------
    # Vrai lien Facebook
    # ------------------------------------------

    if valid_final_url(url):

        return jsonify(
            success=True,
            final_url=
                clean_facebook_url(url)
        )


    return jsonify(
        success=False,
        error=
            "Ce lien Facebook ne correspond pas "
            "à un profil exploitable."
    ), 400


# ==========================================================
# LANCEMENT LOCAL
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
