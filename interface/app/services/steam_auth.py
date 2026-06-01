import secrets
import time

import requests
from base64 import b64encode
from rsa import PublicKey, encrypt as rsa_encrypt

STEAM_API_URL       = "https://api.steampowered.com"
STEAM_COMMUNITY_URL = "https://steamcommunity.com"
STEAM_LOGIN_URL     = "https://login.steampowered.com"

_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         f"{STEAM_COMMUNITY_URL}/",
    "Origin":          STEAM_COMMUNITY_URL,
}


def _post(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """POST with one automatic retry on 429."""
    resp = session.post(url, headers=_HEADERS, **kwargs)
    if resp.status_code == 429:
        time.sleep(5)
        resp = session.post(url, headers=_HEADERS, **kwargs)
    if resp.status_code == 429:
        raise ValueError(
            "Steam ograniczył liczbę prób logowania. Poczekaj kilka minut i spróbuj ponownie."
        )
    resp.raise_for_status()
    return resp


def steam_login(username: str, password: str, guard_code: str) -> dict:
    """Performs full Steam login flow and returns sessionid + steamLoginSecure cookies."""
    session = requests.Session()

    # Initialize session cookies on steamcommunity.com
    session.get(STEAM_COMMUNITY_URL, headers=_HEADERS, timeout=10)
    time.sleep(1)

    # Reuse the sessionid Steam gave us — passing a mismatched value confuses the flow
    session_id = session.cookies.get("sessionid") or secrets.token_hex(12)

    # 1. RSA public key for password encryption
    resp = session.get(
        f"{STEAM_API_URL}/IAuthenticationService/GetPasswordRSAPublicKey/v1",
        params={"account_name": username},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    key = resp.json()["response"]
    pub_key = PublicKey(int(key["publickey_mod"], 16), int(key["publickey_exp"], 16))
    encrypted_pw = b64encode(rsa_encrypt(password.encode("utf-8"), pub_key)).decode()

    time.sleep(1)

    # 2. Begin auth session
    resp = _post(
        session,
        f"{STEAM_API_URL}/IAuthenticationService/BeginAuthSessionViaCredentials/v1",
        data={
            "persistence":          "1",
            "encrypted_password":   encrypted_pw,
            "account_name":         username,
            "encryption_timestamp": key["timestamp"],
        },
        timeout=10,
    )
    auth = resp.json().get("response", {})
    if not auth.get("client_id"):
        raise ValueError("Nieprawidłowy login lub hasło")

    # 3. Submit Steam Guard code (type 3 = Mobile Authenticator)
    _post(
        session,
        f"{STEAM_API_URL}/IAuthenticationService/UpdateAuthSessionWithSteamGuardCode/v1",
        data={
            "client_id": auth["client_id"],
            "steamid":   auth["steamid"],
            "code_type": 3,
            "code":      guard_code.upper().strip(),
        },
        timeout=10,
    )

    # 4. Poll for refresh token
    resp = _post(
        session,
        f"{STEAM_API_URL}/IAuthenticationService/PollAuthSessionStatus/v1",
        data={
            "client_id":  auth["client_id"],
            "request_id": auth["request_id"],
        },
        timeout=10,
    )
    poll = resp.json().get("response", {})
    refresh_token = poll.get("refresh_token", "")
    access_token  = poll.get("access_token", "")
    if not refresh_token:
        raise ValueError("Nieprawidłowy kod Steam Guard lub kod wygasł")

    # 5. Finalize login — use the same sessionid Steam already gave us
    resp = _post(
        session,
        f"{STEAM_LOGIN_URL}/jwt/finalizelogin",
        data={
            "nonce":     refresh_token,
            "sessionid": session_id,
            "redir":     f"{STEAM_COMMUNITY_URL}/login/home/?goto=",
        },
        timeout=10,
    )
    finalize_json = resp.json()

    # 6. Follow transfer redirects to propagate cookies across Steam domains
    for transfer in finalize_json.get("transfer_info", []):
        session.post(transfer["url"], data=transfer["params"], headers=_HEADERS, timeout=10)

    # 7. Extract cookies
    all_cookies      = {c.name: c.value for c in session.cookies}
    sessionid_val    = all_cookies.get("sessionid", "")
    login_secure_val = all_cookies.get("steamLoginSecure", "")

    # settoken doesn't always propagate steamLoginSecure into the requests cookie jar —
    # construct it from the access_token returned by PollAuthSessionStatus
    if not login_secure_val and access_token:
        steamid = auth.get("steamid", finalize_json.get("steamID", ""))
        login_secure_val = f"{steamid}||{access_token}"

    if not sessionid_val or not login_secure_val:
        raise ValueError("Logowanie nieudane – nie otrzymano ciasteczek sesji od Steam")

    return {"sessionid": sessionid_val, "steamLoginSecure": login_secure_val}
