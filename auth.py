from config import COOKIE_FILE, tr
from api import SfacgClient
from ui import safe_print

def load_cookie() -> str:
    if not COOKIE_FILE.exists():
        COOKIE_FILE.write_text("", encoding="utf-8")
        safe_print(tr("cookie_created"))
        return ""
    safe_print(tr("loading_cookie"))
    cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
    safe_print(f"{tr('cookie_read')} {cookie}")
    return cookie

def save_cookie(cookie: str) -> None:
    safe_print(tr("saving_cookie"))
    COOKIE_FILE.write_text(cookie, encoding="utf-8")

def ensure_login(client: SfacgClient) -> bool:
    safe_print(tr("checking_login"))
    cookie = load_cookie()
    client.set_cookie_string(cookie)
    if cookie:
        safe_print(tr("using_saved_cookie"))
        if client.check_login():
            safe_print(tr("login_ok"))
            return True
    while True:
        username = input(tr("input_phone")).strip()
        password = input(tr("input_password")).strip()
        safe_print(tr("logging_in"))
        cookie = client.login(username, password)
        if cookie != "error":
            client.set_cookie_string(cookie)
            if client.check_login():
                save_cookie(cookie)
                safe_print(tr("login_ok"))
                return True
        client.set_cookie_string("")
        safe_print(tr("login_failed"))
