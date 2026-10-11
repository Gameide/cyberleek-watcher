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

def load_settings():
    defaults = {
        "telegram_token": "YOUR_BOT_TOKEN_HERE",
        "telegram_chat_id": "YOUR_CHAT_ID_HERE",
        "auto_open_browser": True,
        "play_audio_alert": True,
        "rpc_url": "https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY",
        "rpc_ws_url": "wss://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY"
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
    cfg.setdefault("rpc_url", "https://api.mainnet-beta.solana.com")
    cfg.setdefault("rpc_ws_url", "wss://api.mainnet-beta.solana.com")
    return cfg

settings = load_settings()
TELEGRAM_TOKEN = settings["telegram_token"]
TELEGRAM_CHAT_ID = str(settings["telegram_chat_id"])
AUTO_OPEN_BROWSER = settings["auto_open_browser"]
PLAY_AUDIO_ALERT = settings["play_audio_alert"]
RPC_URL = settings["rpc_url"]
RPC_WS_URL = settings["rpc_ws_url"]

CURRENT_VERSION = "3.2.0"
VERSION_URL = "https://raw.githubusercontent.com/Gameide/cyberleek-watcher/refs/heads/main/version.txt"
GITHUB_REPO_URL = "https://github.com/Gameide/cyberleek-watcher"

ANCHOR = "7rAgHPLDc9NryZmNdeEzyDui6D9PHkvTxMjKhNSa7w3a"
MINT = "ApZuxdpzMrbEYTGEzeY9afh5pj9d6qPRJCTgQYiipbKg"
CONTENT_DISCRIMINATOR = "G6JNBZ2BSey"
POLL_DISCRIMINATOR = "5Qpj1hsHT4k"

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

    def answer_callback(self, callback_id, text=None):
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            self.session.post(f"{self.base}/answerCallbackQuery", json=payload, timeout=10)
        except Exception:
            pass

    def get_updates(self):
        try:
            r = self.session.get(f"{self.base}/getUpdates", params={"offset": self.offset, "timeout": 20}, timeout=25)
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
        self.running = True
        self.ws_connected = False
        self.menu_message_id = None

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

    def main_menu_markup(self):
        return {
            "inline_keyboard": [
                [{"text": "🔥 Latest Leek", "callback_data": "latest_leek"}],
                [{"text": "📊 Active Polls", "callback_data": "polls"}],
                [{"text": "📈 Status", "callback_data": "status"}],
                [{"text": "🔄 Refresh", "callback_data": "refresh"}]
            ]
        }

    def send_main_menu(self):
        text = "🟢 <b>Cyberleek Monitor</b>\n\nChoose an option:"
        mid = self.tg.send_message(text, self.main_menu_markup())
        if mid:
            self.menu_message_id = mid

    def format_poll(self, title, choices, bals, total, ends):
        live = datetime.now().timestamp() < ends
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
        text = self.format_poll(title, choices, bals, total, ends)
        now = time.time()
        if pk not in self.active_polls:
            if not self.is_first_run:
                mid = self.tg.send_message(text)
                self.active_polls[pk] = {"msg_id": mid, "last_total": total, "last_edit": now}
            else:
                self.active_polls[pk] = {"msg_id": None, "last_total": total, "last_edit": now}
        else:
            info = self.active_polls[pk]
            if total != info["last_total"] or now - info["last_edit"] > 120:
                mid = info.get("msg_id")
                if mid:
                    self.executor.submit(self.tg.edit_message, mid, text)
                info["last_total"] = total
                info["last_edit"] = now

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

    def handle_callback(self, data, callback_id, message_id):
        self.tg.answer_callback(callback_id)
        if data == "latest_leek":
            if self.latest_leek:
                leek = self.latest_leek
                text = f"🔥 <b>Latest Leek</b>\n\n📌 {leek['title']}\n🕒 {datetime.fromtimestamp(leek['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n"
                kb = [[{"text": f"🔗 {it['label'][:30]}", "url": it["url"]}] for it in leek.get("items", [])[:6]]
                kb.append([{"text": "« Back", "callback_data": "menu"}])
                self.tg.edit_message(message_id, text, {"inline_keyboard": kb})
            else:
                self.tg.edit_message(message_id, "No leaks yet.", {"inline_keyboard": [[{"text": "« Back", "callback_data": "menu"}]]})
        elif data == "polls":
            if self.polls:
                text = "📊 <b>Active Polls</b>\n\n"
                kb = []
                for p in self.polls[:5]:
                    live = datetime.now().timestamp() < p["ends_at"]
                    status = "🟢" if live else "🔴"
                    text += f"{status} {p['title'][:40]}\n"
                    kb.append([{"text": f"{status} {p['title'][:25]}", "callback_data": f"poll_{p['pubkey'][:8]}"}])
                kb.append([{"text": "« Back", "callback_data": "menu"}])
                self.tg.edit_message(message_id, text, {"inline_keyboard": kb})
            else:
                self.tg.edit_message(message_id, "No active polls.", {"inline_keyboard": [[{"text": "« Back", "callback_data": "menu"}]]})
        elif data.startswith("poll_"):
            short = data[5:]
            p = next((x for x in self.polls if x["pubkey"].startswith(short)), None)
            if p:
                text = self.format_poll(p["title"], p["choices"], p["balances"], p["total"], p["ends_at"])
                self.tg.edit_message(message_id, text, {"inline_keyboard": [[{"text": "« Back", "callback_data": "polls"}]]})
        elif data == "status":
            uptime = str(datetime.now() - self.start_time).split('.')[0]
            text = f"📈 <b>Status</b>\n\nUptime: {uptime}\nScans: {self.scans}\nWS: {'Connected' if self.ws_connected else 'Disconnected'}\nLeaks tracked: {len(self.leaks)}\nPolls: {len(self.polls)}\nLast change: {self.last_change}"
            self.tg.edit_message(message_id, text, {"inline_keyboard": [[{"text": "« Back", "callback_data": "menu"}]]})
        elif data in ("menu", "refresh"):
            self.tg.edit_message(message_id, "🟢 <b>Cyberleek Monitor</b>\n\nChoose an option:", self.main_menu_markup())

    def telegram_listener(self):
        while self.running:
            updates = self.tg.get_updates()
            for upd in updates:
                self.tg.offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    if str(cq["message"]["chat"]["id"]) == TELEGRAM_CHAT_ID:
                        self.handle_callback(cq["data"], cq["id"], cq["message"]["message_id"])
            time.sleep(0.5)

    async def ws_loop(self):
        filters_c = [{"memcmp": {"offset": 0, "bytes": CONTENT_DISCRIMINATOR}}]
        filters_p = [{"memcmp": {"offset": 0, "bytes": POLL_DISCRIMINATOR}}]
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
                self.log(f"{C.YELLOW}WS reconnect: {str(e)[:60]}{C.RESET}")
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
        self.is_first_run = False
        self.log(f"{C.GREEN}Bootstrap done.{C.RESET}")

    def run(self):
        self.bootstrap()
        self.send_main_menu()
        threading.Thread(target=self.telegram_listener, daemon=True).start()
        def start_ws():
            asyncio.run(self.ws_loop())
        threading.Thread(target=start_ws, daemon=True).start()
        while self.running:
            self.draw_dashboard()
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
