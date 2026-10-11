import os
import sys
import subprocess
import json
import time
import struct
import base64
import threading
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import webbrowser

def check_dependencies():
    required = ["requests", "solders", "websockets"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        os.execv(sys.executable, [sys.executable] + sys.argv)

check_dependencies()

import requests
from solders.pubkey import Pubkey
import websockets

SETTINGS_FILE = "settings.json"
SCRIPT_URL = "https://raw.githubusercontent.com/Gameide/cyberleek-watcher/refs/heads/main/cyberleekwatcher.py"
VERSION_URL = "https://raw.githubusercontent.com/Gameide/cyberleek-watcher/refs/heads/main/version.txt"

def load_settings():
    defaults = {
        "telegram_token": "YOUR_BOT_TOKEN_HERE",
        "telegram_chat_id": "YOUR_CHAT_ID_HERE",
        "auto_open_browser": True,
        "play_audio_alert": True,
        "auto_update": False,
        "rpc_url": "https://api.mainnet-beta.solana.com",
        "rpc_ws_url": "wss://api.mainnet-beta.solana.com"
    }
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(defaults, f, indent=4)
        print("Created settings.json. Configure it and restart.")
        sys.exit(0)
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("telegram_token") or cfg["telegram_token"].startswith("YOUR_"):
        print("Configure telegram_token and telegram_chat_id in settings.json")
        sys.exit(0)
    cfg.setdefault("auto_open_browser", True)
    cfg.setdefault("play_audio_alert", True)
    cfg.setdefault("auto_update", False)
    cfg.setdefault("rpc_url", "https://api.mainnet-beta.solana.com")
    cfg.setdefault("rpc_ws_url", "wss://api.mainnet-beta.solana.com")
    return cfg

settings = load_settings()
TELEGRAM_TOKEN = settings["telegram_token"]
TELEGRAM_CHAT_ID = str(settings["telegram_chat_id"])
AUTO_OPEN_BROWSER = settings["auto_open_browser"]
PLAY_AUDIO_ALERT = settings["play_audio_alert"]
AUTO_UPDATE = settings["auto_update"]
RPC_URL = settings["rpc_url"]
RPC_WS_URL = settings["rpc_ws_url"]
if RPC_WS_URL.startswith("https://"):
    RPC_WS_URL = "wss://" + RPC_WS_URL[8:]
elif RPC_WS_URL.startswith("http://"):
    RPC_WS_URL = "ws://" + RPC_WS_URL[7:]

CURRENT_VERSION = "3.4.2"

ANCHOR = "7rAgHPLDc9NryZmNdeEzyDui6D9PHkvTxMjKhNSa7w3a"
MINT = "ApZuxdpzMrbEYTGEzeY9afh5pj9d6qPRJCTgQYiipbKg"
CONTENT_DISCRIMINATOR = "G6JNBZ2BSey"
POLL_DISCRIMINATOR = "5Qpj1hsHT4k"
ANNOUNCEMENT_DISCRIMINATOR = "81f55033eeefa06e"

TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
_anchor = Pubkey.from_string(ANCHOR)
_mint = Pubkey.from_string(MINT)

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"
    MAGENTA = "\033[95m"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

class Reader:
    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0
    def u32(self):
        v = struct.unpack_from("<I", self.buf, self.pos)[0]
        self.pos += 4
        return v
    def i64(self):
        v = struct.unpack_from("<q", self.buf, self.pos)[0]
        self.pos += 8
        return v
    def raw(self, n):
        v = self.buf[self.pos:self.pos + n]
        self.pos += n
        return v
    def string(self):
        n = self.u32()
        return self.raw(n).decode("utf-8", "replace")

class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()
        self.offset = 0

    def send_message(self, text, reply_markup=None):
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            r = self.session.post(f"{self.base}/sendMessage", json=payload, timeout=15)
            data = r.json()
            if data.get("ok"):
                return data["result"]["message_id"]
        except Exception:
            pass
        return None

    def edit_message(self, message_id, text, reply_markup=None):
        payload = {"chat_id": self.chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            self.session.post(f"{self.base}/editMessageText", json=payload, timeout=15)
        except Exception:
            pass

    def answer_callback(self, callback_id):
        try:
            self.session.post(f"{self.base}/answerCallbackQuery", json={"callback_query_id": callback_id}, timeout=10)
        except Exception:
            pass

    def get_updates(self):
        try:
            r = self.session.get(f"{self.base}/getUpdates", params={"offset": self.offset, "timeout": 15}, timeout=20)
            data = r.json()
            if data.get("ok"):
                return data["result"]
        except Exception:
            pass
        return []

    def send_document(self, filename, file_bytes):
        try:
            self.session.post(
                f"{self.base}/sendDocument",
                data={"chat_id": self.chat_id, "caption": f"📎 {filename}"},
                files={"document": (filename, file_bytes)},
                timeout=60
            )
        except Exception:
            pass

class CyberleekMonitor:
    def __init__(self):
        self.tg = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
        self.http = requests.Session()
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.known_leaks = set()
        self.active_polls = {}
        self.ata_cache = {}
        self.leaks = []
        self.polls = []
        self.is_first_run = True
        self.start_time = datetime.now()
        self.scans = 0
        self.last_change = "None"
        self.rpc_status = f"{C.GRAY}Connecting...{C.RESET}"
        self.logs = []
        self.latest_leek = None
        self.latest_poll = None
        self.announcements = []
        self.combined_msg_id = None
        self.last_combined_edit = 0
        self.running = True
        self.ws_connected = False
        self.update_notified = False
        self.pending_update = False

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")
        if len(self.logs) > 8:
            self.logs.pop(0)

    def draw_dashboard(self):
        clear()
        uptime = str(datetime.now() - self.start_time).split('.')[0]
        print(f"{C.CYAN}{C.BOLD}")
        print("╔════════════════════════════════════════════════════════════════════════╗")
        print("║       CYBERLEEK ON-CHAIN MONITOR  •  Telegram Bot Integration        ║")
        print(f"╚══════════════════════════════════════════════════════════════════════╝{C.RESET}")
        print(f"\n{C.WHITE}General Status{C.RESET} | Version {CURRENT_VERSION}")
        print(f"  Scans / WS             : {C.BOLD}{self.scans}{C.RESET}  {'🟢 WS' if self.ws_connected else '🟡 Poll'}")
        print(f"  Uptime                 : {C.BOLD}{C.GREEN}{uptime}{C.RESET}")
        print(f"  Last change detected   : {C.YELLOW}{self.last_change}{C.RESET}")
        print(f"  RPC Status             : {self.rpc_status}")
        if self.logs:
            print(f"\n{C.WHITE}{C.BOLD}--- ACTIVITY LOG ---{C.RESET}")
            for l in self.logs:
                print(l)

    def do_update(self):
        try:
            self.log(f"{C.CYAN}Downloading update...{C.RESET}")
            r = self.http.get(SCRIPT_URL, timeout=25)
            if r.status_code != 200 or len(r.content) < 1000:
                self.log(f"{C.RED}Update download failed{C.RESET}")
                return
            with open(__file__, "wb") as f:
                f.write(r.content)
            try:
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                current = {}
            defaults = {
                "telegram_token": "YOUR_BOT_TOKEN_HERE",
                "telegram_chat_id": "YOUR_CHAT_ID_HERE",
                "auto_open_browser": True,
                "play_audio_alert": True,
                "auto_update": False,
                "rpc_url": "https://api.mainnet-beta.solana.com",
                "rpc_ws_url": "wss://api.mainnet-beta.solana.com"
            }
            for k, v in defaults.items():
                if k not in current:
                    current[k] = v
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=4)
            self.log(f"{C.GREEN}Update applied. Restarting...{C.RESET}")
            self.tg.send_message("✅ <b>Update applied.</b> Restarting script...")
            time.sleep(1.5)
            script_path = os.path.abspath(__file__)
            cwd = os.path.dirname(script_path)
            if os.name == "nt":
                subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=cwd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=cwd,
                    start_new_session=True
                )
            time.sleep(0.6)
            os._exit(0)
        except Exception as e:
            self.log(f"{C.RED}Update error: {e}{C.RESET}")

    def check_for_updates(self):
        if self.update_notified:
            return
        try:
            r = self.http.get(VERSION_URL, timeout=8)
            if r.status_code == 200:
                remote = r.text.strip()
                if remote and remote != CURRENT_VERSION:
                    self.update_notified = True
                    if AUTO_UPDATE:
                        self.log(f"{C.YELLOW}New version {remote} found. Auto-updating...{C.RESET}")
                        self.executor.submit(self.do_update)
                    else:
                        self.log(f"{C.YELLOW}New version {remote} available{C.RESET}")
                        markup = {"inline_keyboard": [[{"text": "✅ Yes, update now", "callback_data": "do_update"}]]}
                        self.tg.send_message(
                            f"⚠️ <b>New version available</b>\n\nCurrent: v{CURRENT_VERSION}\nNew: v{remote}\n\nDo you want to update now?",
                            markup
                        )
                        self.pending_update = True
        except Exception:
            pass

    def telegram_listener(self):
        while self.running:
            if not self.pending_update:
                time.sleep(2)
                continue
            updates = self.tg.get_updates()
            for upd in updates:
                self.tg.offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    if str(cq["message"]["chat"]["id"]) == TELEGRAM_CHAT_ID and cq.get("data") == "do_update":
                        self.tg.answer_callback(cq["id"])
                        self.tg.edit_message(cq["message"]["message_id"], "✅ Updating...")
                        self.executor.submit(self.do_update)
                        self.pending_update = False
            time.sleep(1)

    def rpc(self, method, params, timeout=15):
        try:
            r = self.http.post(RPC_URL, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=timeout)
            self.rpc_status = f"{C.GREEN}Online{C.RESET}"
            return r.json().get("result")
        except Exception:
            self.rpc_status = f"{C.RED}Error{C.RESET}"
            return None

    def get_balances(self, pubkeys):
        if not pubkeys:
            return {}
        unique = list(set(pubkeys))
        res = self.rpc("getMultipleAccounts", [unique, {"encoding": "jsonParsed"}])
        out = {}
        if res and "value" in res:
            for pk, acc in zip(unique, res["value"]):
                try:
                    out[pk] = int(acc["data"]["parsed"]["info"]["tokenAmount"]["amount"])
                except Exception:
                    out[pk] = 0
        return out

    def get_ata(self, poll_id: bytes, idx: int) -> str:
        key = (poll_id.hex(), idx)
        if key not in self.ata_cache:
            opt, _ = Pubkey.find_program_address([b"option", poll_id, bytes([idx])], _anchor)
            ata, _ = Pubkey.find_program_address([bytes(opt), bytes(TOKEN_PROGRAM), bytes(_mint)], ATA_PROGRAM)
            self.ata_cache[key] = str(ata)
        return self.ata_cache[key]

    def send_announcement(self, ann):
        ts_str = datetime.fromtimestamp(ann["timestamp"]).strftime("%Y-%m-%d %H:%M")
        text = f"📢 <b>ANNOUNCEMENT</b>\n\n<b>{ann['title']}</b>\n🕒 {ts_str}\n\n{ann.get('body','')[:600]}"
        self.executor.submit(self.tg.send_message, text)

    def build_combined_message(self):
        now_dt = datetime.now()
        parts = []
        kb = []
        if self.latest_leek:
            leek = self.latest_leek
            parts.append(f"🔥 <b>Latest Leek</b>\n📌 {leek['title']}\n🕒 {datetime.fromtimestamp(leek['timestamp']).strftime('%H:%M:%S')}")
            for it in leek.get("items", [])[:6]:
                label = it.get("label", "Open")[:28]
                url = it.get("url", "")
                if url:
                    kb.append([{"text": f"🔗 {label}", "url": url}])
        live = [p for p in self.polls if now_dt.timestamp() < p.get("ends_at", 0)]
        if live:
            p = live[0]
            parts.append("\n" + self.format_poll(p["title"], p["choices"], p["balances"], p["total"], p["ends_at"]))
        else:
            parts.append("\n📊 No live polls right now.")
        parts.append(f"\n🕒 Updated: {now_dt.strftime('%H:%M:%S')}")
        markup = {"inline_keyboard": kb} if kb else None
        return "\n".join(parts), markup

    def update_combined_message(self):
        text, markup = self.build_combined_message()
        now = time.time()
        if self.combined_msg_id is None:
            mid = self.tg.send_message(text, markup)
            if mid:
                self.combined_msg_id = mid
                self.last_combined_edit = now
        elif now - self.last_combined_edit > 30:
            self.executor.submit(self.tg.edit_message, self.combined_msg_id, text, markup)
            self.last_combined_edit = now

    def format_poll(self, title, choices, bals, total, ends):
        now_dt = datetime.now()
        live = now_dt.timestamp() < ends
        status = "🟢 LIVE" if live else "🔴 ENDED"
        txt = f"📊 <b>{status} POLL</b>\n\n<b>{title}</b>\n"
        for i, c in enumerate(choices):
            bal = bals[i] / 1e9
            pct = (bals[i] / total * 100) if total else 0
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            txt += f"▪️ <b>{c}</b>\n   {bar} {pct:.1f}% ({bal:,.0f})\n"
        txt += f"\n💰 Total: {total / 1e9:,.0f} $CYBERLEEK"
        return txt

    def process_account(self, pubkey: str, data_b64: str):
        try:
            raw = base64.b64decode(data_b64)
            if len(raw) < 16:
                return
            disc_hint = base64.b64encode(raw[:12]).decode()
            t = Reader(raw[8:])
            t.raw(32)
            ts = t.i64()
            if CONTENT_DISCRIMINATOR in disc_hint or len(raw) > 6500:
                title = t.string()
                n = t.u32()
                items = [{"label": t.string(), "url": t.string()} for _ in range(min(n, 20))]
                entry = {"timestamp": ts, "title": title, "items": items}
                if ts not in self.known_leaks:
                    self.known_leaks.add(ts)
                    self.leaks.append(entry)
                    self.leaks.sort(key=lambda x: x["timestamp"], reverse=True)
                    self.leaks = self.leaks[:30]
                    if not self.is_first_run:
                        self.last_change = datetime.now().strftime("%H:%M:%S")
                        self.log(f"{C.GREEN}🚀 NEW LEEK: {title}{C.RESET}")
                        if PLAY_AUDIO_ALERT:
                            try:
                                import winsound
                                winsound.Beep(1400, 200)
                                winsound.Beep(1800, 300)
                            except Exception:
                                pass
                        for item in items:
                            if AUTO_OPEN_BROWSER:
                                try:
                                    webbrowser.open(item["url"])
                                except Exception:
                                    pass
                            self.executor.submit(self.download_and_send, item["url"], item["label"], title)
                    if not self.latest_leek or ts > self.latest_leek["timestamp"]:
                        self.latest_leek = entry
            elif ANNOUNCEMENT_DISCRIMINATOR in disc_hint or (ANNOUNCEMENT_DISCRIMINATOR[:8] in disc_hint):
                try:
                    title = t.string()
                    body = t.string() if t.pos < len(raw) - 20 else ""
                    entry = {"timestamp": ts, "title": title, "body": body}
                    if ts not in [a.get("timestamp") for a in self.announcements]:
                        self.announcements.append(entry)
                        self.announcements.sort(key=lambda x: x["timestamp"], reverse=True)
                        self.announcements = self.announcements[:10]
                        if not self.is_first_run:
                            self.log(f"{C.MAGENTA}📢 ANNOUNCEMENT: {title}{C.RESET}")
                            self.send_announcement(entry)
                except Exception:
                    pass
            elif POLL_DISCRIMINATOR in disc_hint or (2500 < len(raw) < 4000):
                poll_id = t.raw(32)
                title = t.string()
                n = t.u32()
                choices = [t.string() for _ in range(min(n, 10))]
                ends = t.i64()
                atas = [self.get_ata(poll_id, i) for i in range(len(choices))]
                bals_map = self.get_balances(atas)
                bals = [bals_map.get(a, 0) for a in atas]
                total = sum(bals)
                entry = {"pubkey": pubkey, "timestamp": ts, "title": title, "choices": choices, "ends_at": ends, "balances": bals, "total": total}
                existing = next((p for p in self.polls if p["pubkey"] == pubkey), None)
                if existing:
                    existing.update(entry)
                else:
                    self.polls.append(entry)
                self.polls.sort(key=lambda x: x["timestamp"], reverse=True)
                self.polls = self.polls[:15]
                if not self.latest_poll or ts > self.latest_poll.get("timestamp", 0):
                    self.latest_poll = entry
                self.update_poll_msg(pubkey, title, choices, bals, total, ends)
        except Exception:
            pass

    def update_poll_msg(self, pk, title, choices, bals, total, ends):
        pass

    def download_and_send(self, url, label, title):
        fn = label.replace(" ", "_") or "file"
        if "." not in fn:
            fn += ".mp4"
        text = f"🚨 <b>NEW LEEK</b>\n\n📌 {title}\n🎬 {fn}"
        markup = {"inline_keyboard": [[{"text": "🔗 Open", "url": url}]]}
        self.executor.submit(self.tg.send_message, text, markup)
        if any(h in url.lower() for h in ["arweave.net", "temp.sh"]):
            try:
                r = self.http.get(url, timeout=30)
                size = int(r.headers.get("Content-Length", 0))
                if 0 < size <= 50 * 1024 * 1024:
                    self.executor.submit(self.tg.send_document, fn, r.content)
            except Exception:
                pass

    def send_startup_data(self):
        for ann in self.announcements[:5]:
            self.send_announcement(ann)
        self.update_combined_message()
        if not self.latest_leek and not self.polls and not self.announcements:
            self.tg.send_message("🟢 <b>Cyberleek Monitor started</b>\n\nNo content yet.")

    async def ws_loop(self):
        filters_c = [{"memcmp": {"offset": 0, "bytes": CONTENT_DISCRIMINATOR}}]
        filters_p = [{"memcmp": {"offset": 0, "bytes": POLL_DISCRIMINATOR}}]
        filters_a = [{"memcmp": {"offset": 0, "bytes": ANNOUNCEMENT_DISCRIMINATOR}}]
        while self.running:
            try:
                async with websockets.connect(RPC_WS_URL, ping_interval=25, ping_timeout=20) as ws:
                    self.ws_connected = True
                    self.rpc_status = f"{C.GREEN}WS Connected{C.RESET}"
                    self.log(f"{C.CYAN}WebSocket connected{C.RESET}")
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": 1, "method": "programSubscribe",
                        "params": [ANCHOR, {"encoding": "base64", "filters": filters_c, "commitment": "confirmed"}]
                    }))
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": 2, "method": "programSubscribe",
                        "params": [ANCHOR, {"encoding": "base64", "filters": filters_p, "commitment": "confirmed"}]
                    }))
                    await ws.send(json.dumps({
                        "jsonrpc": "2.0", "id": 3, "method": "programSubscribe",
                        "params": [ANCHOR, {"encoding": "base64", "filters": filters_a, "commitment": "confirmed"}]
                    }))
                    async for raw_msg in ws:
                        if not self.running:
                            break
                        data = json.loads(raw_msg)
                        if data.get("method") == "programNotification":
                            val = data["params"]["result"]["value"]
                            self.executor.submit(self.process_account, val["pubkey"], val["account"]["data"][0])
            except Exception as e:
                self.ws_connected = False
                self.rpc_status = f"{C.YELLOW}WS reconnecting...{C.RESET}"
                err = str(e)
                if "api-key" in err.lower() or "helius" in err.lower() or len(err) > 40:
                    err = "connection failed (check rpc_ws_url)"
                self.log(f"{C.YELLOW}WS reconnect: {err[:50]}{C.RESET}")
                await asyncio.sleep(4)

    def bootstrap(self):
        self.log("Bootstrapping...")
        res = self.rpc("getProgramAccounts", [ANCHOR, {"encoding": "base64", "filters": [{"memcmp": {"offset": 0, "bytes": CONTENT_DISCRIMINATOR}}]}])
        if res:
            for acc in res:
                self.process_account(acc["pubkey"], acc["account"]["data"][0])
        res = self.rpc("getProgramAccounts", [ANCHOR, {"encoding": "base64", "filters": [{"memcmp": {"offset": 0, "bytes": POLL_DISCRIMINATOR}}]}])
        if res:
            for acc in res:
                self.process_account(acc["pubkey"], acc["account"]["data"][0])
        res = self.rpc("getProgramAccounts", [ANCHOR, {"encoding": "base64", "filters": [{"memcmp": {"offset": 0, "bytes": ANNOUNCEMENT_DISCRIMINATOR}}]}])
        if res:
            for acc in res:
                self.process_account(acc["pubkey"], acc["account"]["data"][0])
        self.send_startup_data()
        self.is_first_run = False
        self.log(f"{C.GREEN}Bootstrap done.{C.RESET}")

    def run(self):
        self.bootstrap()
        threading.Thread(target=self.telegram_listener, daemon=True).start()
        def start_ws():
            asyncio.run(self.ws_loop())
        threading.Thread(target=start_ws, daemon=True).start()
        while self.running:
            self.draw_dashboard()
            if self.scans % 15 == 0:
                self.executor.submit(self.update_combined_message)
            if self.scans % 30 == 0:
                self.executor.submit(self.check_for_updates)
            if self.scans % 20 == 0 and not self.ws_connected:
                self.executor.submit(self.bootstrap)
            time.sleep(2)
            self.scans += 1

if __name__ == "__main__":
    mon = CyberleekMonitor()
    try:
        mon.run()
    except KeyboardInterrupt:
        mon.running = False
        print("\nStopped.")
