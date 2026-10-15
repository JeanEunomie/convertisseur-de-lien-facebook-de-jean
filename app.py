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
                +
