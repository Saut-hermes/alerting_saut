import hashlib
import json
import os
import requests
from bs4 import BeautifulSoup

URL = "https://www.sauthermes.com/fr/billetterie/"
STATE_FILE = "state.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
}


def extract_content_hash(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("main") or soup.body
    if container is None:
        raise ValueError("Missing body element in HTML response")

    for tag in container(["script", "style", "noscript"]):
        tag.decompose()

    clean_text = " ".join(container.get_text(separator=" ").split())
    digest = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
    return digest, clean_text


def send_ntfy_alert(text_preview: str) -> None:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("Missing NTFY_TOPIC environment variable")

    endpoint = f"https://ntfy.sh/{topic}"
    body = f"Changement détecté sur la billetterie : {URL}\n\nExtrait : {text_preview[:200]}"
    headers = {
        "Title": "Saut Hermes - Billetterie",
        "Priority": "high",
        "Tags": "ticket,horse_racing",
    }
    resp = requests.post(endpoint, data=body.encode("utf-8"), headers=headers, timeout=20)
    resp.raise_for_status()


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=20)
    response.raise_for_status()

    new_hash, clean_text = extract_content_hash(response.text)

    previous_hash = None
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            previous_hash = data.get("sha256")

    if previous_hash is None:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"sha256": new_hash}, f, indent=2)
        print("Initial snapshot saved.")
        return

    if new_hash != previous_hash:
        send_ntfy_alert(clean_text)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"sha256": new_hash}, f, indent=2)
        print("Change detected and ntfy alert sent.")
    else:
        print("No change detected.")


if __name__ == "__main__":
    main()
