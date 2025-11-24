import requests

URL = "https://www.pro-football-reference.com/players/B/BradTo00.htm"

def fetch_brady_stats(url: str) -> None:
    # PFR will often 403 if you don't send a User-Agent
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    print(resp.text)

if __name__ == "__main__":
    fetch_brady_stats(URL)
