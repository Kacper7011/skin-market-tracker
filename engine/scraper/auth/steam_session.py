import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB  = os.getenv("MONGO_DB", "skin_market")

logger = logging.getLogger(__name__)


class SteamSession:
    def __init__(self) -> None:
        self._cookies: dict = {}
        self._logged_in: bool = False

    def login(self) -> bool:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            db = client[MONGO_DB]
            auth = db.steam_auth.find_one({}, sort=[("logged_in_at", -1)])
            client.close()

            if auth and auth.get("sessionid") and auth.get("steamLoginSecure"):
                self._cookies = {
                    "sessionid":        auth["sessionid"],
                    "steamLoginSecure": auth["steamLoginSecure"],
                }
                self._logged_in = True
                logger.info("Załadowano sesję Steam z bazy (użytkownik: %s)", auth.get("username", "?"))
                return True
        except Exception as exc:
            logger.error("Błąd przy ładowaniu sesji Steam z bazy: %s", exc)

        logger.warning("Brak aktywnej sesji Steam – zaloguj się przez panel web: /auth/steam")
        return False

    def get_cookies(self) -> dict:
        if not self._logged_in:
            self.login()
        return self._cookies

    def refresh(self) -> bool:
        self._cookies   = {}
        self._logged_in = False
        return self.login()


steam_session = SteamSession()
