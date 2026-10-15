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
        "(KHTML, like Gecko) "
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
        path = urlparse(url).path.lower().rstrip("/")

        return (
            path == "/login"
            or path == "/login.php"
        )
    except Exception:
        return False


def extract_next(url):
    try:
        qs = parse_qs(urlparse(url).query)

        if not qs.get("next"):
            return None

        destination = unquote(qs["next"][0])

        if facebook_url(destination):
            return destination

    except Exception:
        pass

    return None


def clean_facebook_url(url):
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)

        path = p.path.rstrip("/") or "/"

        # ---------------------------------
        # profile.php?id=...
        # ---------------------------------

        if path.lower() == "/profile.php" and qs.get("id"):

            fb_id = qs["id"][0]

            if fb_id.isdigit():
                return (
                    "https://www.facebook.com/"
                    "profile.php?id=" + fb_id
                )

        # ---------------------------------
        # Nettoyage des paramètres inutiles
        # ---------------------------------

        keep = {}

        for key in (
            "id",
            "story_fbid",
            "fbid",
            "v"
        ):
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

        p = urlparse(url)

        if not p.path.lower().startswith("/people/"):
            return None

        response = requests.get(
            url,
            timeout=12,
            allow_redirects=True,
            headers=HEADERS
        )

        final_url = response.url

        # Facebook a éventuellement redirigé
        # vers profile.php?id=...

        fp = urlparse(final_url)
        fqs = parse_qs(fp.query)

        if (
            fp.path.rstrip("/").lower() == "/profile.php"
            and fqs.get("id")
        ):

            fb_id = fqs["id"][0]

            if fb_id.isdigit():
                return fb_id

        # Sinon recherche dans la page

        return find_numeric_id(response.text)

    except requests.RequestException:
        return None


@app.get("/")
def index():

    return send_from_directory(
        ".",
        "index.html"
    )


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

        login_seen = False

        possible_destination = None


        # =====================================
        # ÉTAPE 1
        # Résolution classique comme avant
        # =====================================

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

            next_url = urljoin(
                current,
                location
            )

            if not facebook_url(next_url):
                break


            # =================================
            # LOGIN rencontré
            # =================================

            if is_login_url(next_url):

                login_seen = True

                destination = extract_next(next_url)

                # On mémorise NEXT mais on ne
                # déclenche PAS encore le bouton orange.

                if destination:

                    possible_destination = destination

                    # Si NEXT contient déjà une vraie
                    # destination autre que /share/
                    # on peut continuer avec elle.

                    destination_path = (
                        urlparse(destination)
                        .path
                        .lower()
                    )

                    if (
                        "/share/" not in destination_path
                        and not is_login_url(destination)
                    ):

                        current = destination
                        continue

                # On arrête cette chaîne de redirection,
                # mais on essaiera encore d'autres méthodes.
                break


            current = next_url


        # =====================================
        # ÉTAPE 2
        # Vérifier si on a déjà un vrai profil
        # =====================================

        if (
            not is_login_url(current)
            and "/share/" not in
            urlparse(current).path.lower()
        ):

            cleaned = clean_facebook_url(current)


            # /people/.../pfbid...
            # tentative ID numérique

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


        # =====================================
        # ÉTAPE 3
        # Essayer la destination NEXT
        # =====================================

        if possible_destination:

            destination_path = (
                urlparse(possible_destination)
                .path
                .lower()
            )

            if (
                "/share/" not in destination_path
                and not is_login_url(possible_destination)
            ):

                cleaned = clean_facebook_url(
                    possible_destination
                )

                return jsonify(
                    status="success",
                    final_url=cleaned
                )


        # =====================================
        # ÉTAPE 4
        # Dernière tentative :
        # laisser requests suivre lui-même
        # toutes les redirections
        # =====================================

        try:

            final_response = requests.get(
                original_url,
                timeout=12,
                allow_redirects=True,
                headers=HEADERS
            )

            final_url = final_response.url

            final_path = (
                urlparse(final_url)
                .path
                .lower()
            )


            if (
                facebook_url(final_url)
                and not is_login_url(final_url)
                and "/share/" not in final_path
            ):

                cleaned = clean_facebook_url(
                    final_url
                )


                if (
                    urlparse(cleaned)
                    .path
                    .lower()
                    .startswith("/people/")
                ):

                    fb_id = try_people_numeric(
                        cleaned
                    )

                    if fb_id:

                        cleaned = (
                            "https://www.facebook.com/"
                            "profile.php?id="
                            + fb_id
                        )


                return jsonify(
                    status="success",
                    final_url=cleaned
                )


        except requests.RequestException:
            pass


        # =====================================
        # ÉTAPE 5
        # Aucune méthode n'a fonctionné.
        #
        # SEULEMENT MAINTENANT :
        # bouton orange
        # =====================================

        return jsonify(

            status="login_required",

            message=(
                "Facebook demande d'ouvrir "
                "ce lien dans ton navigateur."
            ),

            browser_url=original_url

        ), 200


    except requests.RequestException:

        # Même en cas de blocage réseau Facebook,
        # on permet l'ouverture manuelle.

        return jsonify(

            status="login_required",

            message=(
                "Facebook n'a pas permis la "
                "conversion automatique."
            ),

            browser_url=original_url

        ), 200
