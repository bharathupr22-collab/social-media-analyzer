def detect_platform(url: str):
    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return None

        hostname = hostname.lower()

        if "instagram.com" in hostname:
            return "Instagram"

        return None

    except Exception:
        return None


def extract_identifier(url: str, platform: str):
    parsed_url = urlparse(url)
    path = parsed_url.path.strip("/")

    if not path:
        return None

    parts = path.split("/")

    if platform == "Instagram":
        return parts[0]

    return None
