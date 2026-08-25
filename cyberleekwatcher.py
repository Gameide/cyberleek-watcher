import os
import sys
import subprocess
import json


def check_dependencies():
    required_packages = ["requests", "solders"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
            
    if missing_packages:
        print(f"📦 Missing dependencies detected: {', '.join(missing_packages)}")
        print("⏳ Installing automatically, please wait...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
            print("✅ Installation complete! Restarting script...\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"❌ Failed to install automatically: {e}")
            print("Please install manually by typing: pip install requests solders")
            sys.exit(1)

check_dependencies()


SETTINGS_FILE = "settings.json"

def load_settings():
    default_settings = {
        "telegram_token": "YOUR_BOT_TOKEN_HERE",
        "telegram_chat_id": "YOUR_CHAT_ID_HERE",
        "auto_open_browser": True,
        "play_audio_alert": True
    }
    
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, indent=4)
        print(f"⚠️ '{SETTINGS_FILE}' was not found. A default template has been created.")
        print(f"👉 Please open '{SETTINGS_FILE}', enter your Telegram credentials, and run the script again.")
        sys.exit(0)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            
        token = cfg.get("telegram_token", "")
        chat_id = cfg.get("telegram_chat_id", "")
        
        if token == "YOUR_BOT_TOKEN_HERE" or not token or not chat_id:
            print(f"⚠️ Please configure your 'telegram_token' and 'telegram_chat_id' inside '{SETTINGS_FILE}'.")
            sys.exit(0)
            

        if "auto_open_browser" not in cfg:
            cfg["auto_open_browser"] = True
        if "play_audio_alert" not in cfg:
            cfg["play_audio_alert"] = True
            
        return cfg
    except Exception as e:
        print(f"❌ Error loading '{SETTINGS_FILE}': {e}")
        sys.exit(1)

settings = load_settings()
TELEGRAM_TOKEN = settings["telegram_token"]
TELEGRAM_CHAT_ID = str(settings["telegram_chat_id"])
AUTO_OPEN_BROWSER = settings["auto_open_browser"]
PLAY_AUDIO_ALERT = settings["play_audio_alert"]

import time
import struct
import base64
from datetime import datetime
import requests
from solders.pubkey import Pubkey
import webbrowser


SCAN_INTERVAL = 2.5
RPC_URL = "https://api.mainnet-beta.solana.com"


CURRENT_VERSION = "2.0.0"
VERSION_URL = "https://raw.githubusercontent.com/Gameide/cyberleek-watcher/refs/heads/main/version.txt"
GITHUB_REPO_URL = "https://github.com/Gameide/cyberleek-watcher/tree/main"

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
    def u8(self) -> int:
        v = self.buf[self.pos]
        self.pos += 1
        return v
    def u32(self) -> int:
        (v,) = struct.unpack_from("<I", self.buf, self.pos)
        self.pos += 4
        return v
    def u64(self) -> int:
        (v,) = struct.unpack_from("<Q", self.buf, self.pos)
        self.pos += 8
        return v
    def i64(self) -> int:
        (v,) = struct.unpack_from("<q", self.buf, self.pos)
        self.pos += 8
        return v
    def raw(self, n: int) -> bytes:
        v = self.buf[self.pos : self.pos + n]
        self.pos += n
        return v
    def pubkey(self) -> str:
        return str(Pubkey.from_bytes(self.raw(32)))
    def string(self) -> str:
        n = self.u32()
        return self.raw(n).decode("utf-8", "replace")
    def boolean(self) -> bool:
        return self.u8() != 0
    def rem(self) -> int:
        return len(self.buf) - self.pos


class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text, reply_markup=None):
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            res = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10).json()
            if res.get("ok"):
                return res["result"]["message_id"]
        except Exception:
            pass
        return None

    def edit_message(self, message_id, text, reply_markup=None):
        payload = {"chat_id": self.chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        try:
            requests.post(f"{self.base_url}/editMessageText", json=payload, timeout=10)
        except Exception:
            pass

    def send_document(self, filename, file_bytes):
        payload = {"chat_id": self.chat_id, "caption": f"📎 Attached Media\n{filename}"}
        files = {"document": (filename, file_bytes)}
        try:
            requests.post(f"{self.base_url}/sendDocument", data=payload, files=files, timeout=40)
        except Exception:
            pass


class CyberleekMonitor:
    def __init__(self):
        self.tg = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
        self.known_leaks = set()
        self.active_polls = {} 
        self.is_first_run = True
        
        self.start_time = datetime.now()
        self.scans = 0
        self.last_change = "None"
        self.rpc_status = f"{C.GRAY}Waiting...{C.RESET}"
        self.logs = []
        
        self.latest_leek = None
        self.latest_poll = None
        self.update_notified = False

    def log_print(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{now}] {msg}")
        if len(self.logs) > 8:
            self.logs.pop(0)

    def draw_dashboard(self):
        clear()
        uptime = str(datetime.now() - self.start_time).split('.')[0]
        
        print(f"{C.CYAN}{C.BOLD}")
        print(f"╔══════════════════════════════════════════════════════════════════════╗")
        print(f"║       CYBERLEEK ON-CHAIN MONITOR  •  Telegram Bot Integration        ║")
        print(f"╚══════════════════════════════════════════════════════════════════════╝{C.RESET}")
        
        print(f"\n{C.WHITE}General Status{C.RESET} | Version {CURRENT_VERSION}")
        print(f"  Scans                  : {C.BOLD}{self.scans}{C.RESET}")
        print(f"  Uptime                 : {C.BOLD}{C.GREEN}{uptime}{C.RESET}")
        print(f"  Last change detected   : {C.YELLOW}{self.last_change}{C.RESET}")
        print(f"  RPC Status             : {self.rpc_status}")
        
        if self.logs:
            print(f"\n{C.WHITE}{C.BOLD}--- ACTIVITY LOG ---{C.RESET}")
            for log in self.logs:
                print(log)

    def check_for_updates(self):
        if self.update_notified:
            return
            
        try:
            res = requests.get(VERSION_URL, timeout=5)
            if res.status_code == 200:
                remote_version = res.text.strip()
                if remote_version and remote_version != CURRENT_VERSION:
                    self.log_print(f"{C.RED}⚠️ UPDATE FOUND! Remote version: {remote_version}{C.RESET}")
                    
                    msg = f"⚠️ <b>NEW UPDATE AVAILABLE!</b>\n\n<b>Current Version:</b> v{CURRENT_VERSION}\n<b>New Version:</b> v{remote_version}\n\nA new version of the script has been released. Please update your files."
                    markup = {"inline_keyboard": [[{"text": "🔄 Go to GitHub", "url": GITHUB_REPO_URL}]]}
                    self.tg.send_message(msg, markup)
                    
                    self.update_notified = True
        except Exception:
            pass

    def rpc_call(self, method, params):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            res = requests.post(RPC_URL, json=payload, timeout=10)
            self.rpc_status = f"{C.GREEN}Online / Connected{C.RESET}"
            return res.json().get("result")
        except Exception:
            self.rpc_status = f"{C.RED}Connection Error{C.RESET}"
            return None

    def get_token_balance(self, pubkey: str) -> int:
        res = self.rpc_call("getTokenAccountBalance", [pubkey])
        if res and "value" in res:
            return int(res["value"]["amount"])
        return 0

    def get_vote_address(self, poll_id: bytes, choice_index: int) -> str:
        option_pda, _ = Pubkey.find_program_address([b"option", poll_id, bytes([choice_index])], _anchor)
        ata, _ = Pubkey.find_program_address([bytes(option_pda), bytes(TOKEN_PROGRAM), bytes(_mint)], ATA_PROGRAM)
        return str(ata)

    def download_and_send_file(self, url, label, title):
        filename = label.replace(" ", "_")
        if not filename or "." not in filename:
            filename += ".mp4"
            
        self.log_print(f"{C.MAGENTA}Sending text alert to Telegram...{C.RESET}")

        msg_text = f"🚨 <b>NEW ON-CHAIN LEEK!</b>\n\n📌 <b>Title:</b> {title}\n📁 <b>Section:</b> LEEKS\n🎬 <b>File:</b> {filename}"

        
        reply_markup = {"inline_keyboard": [[{"text": "🔗 Open Mirror", "url": url}]]}
        self.tg.send_message(msg_text, reply_markup)
        
        if any(h in url.lower() for h in ["arweave.net", "temp.sh"]):
            self.log_print(f"{C.YELLOW}⏳ Attempting to download: {url}{C.RESET}")
            try:
                head = requests.head(url, timeout=20, allow_redirects=True)
                size_bytes = int(head.headers.get('Content-Length', 0))
                
                if size_bytes <= 52428800:
                    self.log_print(f"{C.CYAN}Size OK ({(size_bytes/1024/1024):.2f} MB). Downloading...{C.RESET}")
                    r = requests.get(url, timeout=30)
                    self.log_print(f"{C.CYAN}Uploading file to Telegram...{C.RESET}")
                    self.tg.send_document(filename, r.content)
                    self.log_print(f"{C.GREEN}✅ File uploaded successfully!{C.RESET}")
                else:
                    self.log_print(f"{C.RED}❌ File too large ({(size_bytes/1024/1024):.2f} MB). Skipping attachment.{C.RESET}")
            except Exception as e:
                self.log_print(f"{C.RED}❌ Download error: {e}{C.RESET}")

    def format_poll_text(self, title, choices, balances, total_votes, ends_at):
        is_live = datetime.now().timestamp() < ends_at
        status = "🟢 LIVE" if is_live else "🔴 ENDED"
        last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        text = f"📊 <b>{status} POLL</b>\n\n<b>{title}</b>\n<i>Ends: {datetime.fromtimestamp(ends_at).strftime('%Y-%m-%d %H:%M')}</i>\n"
        text += f"<i>Last Updated: {last_updated}</i>\n\n"
        
        for i, choice in enumerate(choices):
            bal = balances[i] / (10**9) 
            pct = (balances[i] / total_votes * 100) if total_votes > 0 else 0
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            text += f"▪️ <b>{choice}</b>\n   {bar} {pct:.1f}% ({bal:,.0f} CYBERLEEK(votes)\n"
            
        text += f"\n💰 <b>Total Donated:</b> {total_votes / (10**9):,.0f} $CYBERLEEK"
        return text

    def build_dashboard_msg(self, leek_data, poll_text):
        final_text = "🟢 <b>ON-CHAIN MONITOR STARTED</b>\n\n"
        keyboard = []
        
        if leek_data:
            title = leek_data['title']
            ts = leek_data['timestamp']
            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            final_text += f"🔥 <b>LATEST LEEK PUBLISHED:</b>\n📌 {title}\n🕒 {date_str}\n\n"
            
            for item in leek_data.get('items', []):
                keyboard.append([{"text": f"🔗 {item['label'][:25]}...", "url": item['url']}])
        else:
            final_text += "<i>No previous leaks on-chain.</i>\n\n"
            
        if poll_text:
            final_text += poll_text
        else:
            final_text += "<i>No active polls.</i>"
            
        reply_markup = {"inline_keyboard": keyboard} if keyboard else None
        return final_text, reply_markup

    def scan_leaks(self):
        filters = [{"memcmp": {"offset": 0, "bytes": CONTENT_DISCRIMINATOR}}, {"dataSize": 7156}]
        res = self.rpc_call("getProgramAccounts", [ANCHOR, {"encoding": "base64", "filters": filters}])
        if not res: return
        
        current_leeks = []
        for acc in res:
            raw = base64.b64decode(acc["account"]["data"][0])
            try:
                t = Reader(raw[8:])
                t.pubkey() 
                timestamp = t.i64()
                title = t.string()
                
                count = t.u32()
                items = [{"label": t.string(), "url": t.string()} for _ in range(count)]
                current_leeks.append({'timestamp': timestamp, 'title': title, 'items': items})
                
                if timestamp not in self.known_leaks:
                    if not self.is_first_run:
                        self.last_change = datetime.now().strftime("%H:%M:%S")
                        self.log_print(f"{C.GREEN}🚀 NEW LEEK DETECTED: {title}{C.RESET}")
                        
                        # --- AUDIO ALERTS ---
                        if PLAY_AUDIO_ALERT:
                            try:
                                import winsound
                                winsound.Beep(1400, 300)
                                winsound.Beep(1800, 500)
                                winsound.Beep(2200, 700)
                            except Exception:
                                pass
                        
                        for item in items:
                            if AUTO_OPEN_BROWSER:
                                try:
                                    webbrowser.open(item['url'])
                                    self.log_print(f"{C.CYAN}🌐 Browser opened for link: {item['url'][:30]}...{C.RESET}")
                                except Exception as e:
                                    self.log_print(f"{C.RED}❌ Error opening browser: {e}{C.RESET}")
                            
                            self.download_and_send_file(item['url'], item['label'], title)
                            
                    self.known_leaks.add(timestamp)
            except Exception:
                pass
                
        if self.is_first_run and current_leeks:
            current_leeks.sort(key=lambda x: x['timestamp'], reverse=True)
            self.latest_leek = current_leeks[0]

    def scan_polls(self):
        filters = [{"memcmp": {"offset": 0, "bytes": POLL_DISCRIMINATOR}}, {"dataSize": 2800}]
        res = self.rpc_call("getProgramAccounts", [ANCHOR, {"encoding": "base64", "filters": filters}])
        if not res: return

        current_polls = []
        for acc in res:
            account_pubkey = acc["pubkey"]
            raw = base64.b64decode(acc["account"]["data"][0])
            try:
                t = Reader(raw[8:])
                t.pubkey()
                timestamp = t.i64() 
                poll_id = t.raw(32)
                title = t.string()
                count = t.u32()
                choices = [t.string() for _ in range(count)]
                ends_at = t.i64()
                current_polls.append({
                    'pubkey': account_pubkey, 'timestamp': timestamp, 'poll_id': poll_id,
                    'title': title, 'choices': choices, 'ends_at': ends_at
                })
            except Exception:
                pass
                
        if self.is_first_run and current_polls:
            current_polls.sort(key=lambda x: x['timestamp'], reverse=True)
            self.latest_poll = current_polls[0]

        for p in current_polls:
            balances = []
            for i in range(len(p['choices'])):
                addr = self.get_vote_address(p['poll_id'], i)
                balances.append(self.get_token_balance(addr))
            total = sum(balances)
            self.update_poll_telegram(p['pubkey'], p['title'], p['choices'], balances, total, p['ends_at'])

    def update_poll_telegram(self, acc_pubkey, title, choices, balances, total_votes, ends_at):
        poll_text = self.format_poll_text(title, choices, balances, total_votes, ends_at)
        current_time = time.time()

        if acc_pubkey not in self.active_polls:
            if not self.is_first_run:
                self.last_change = datetime.now().strftime("%H:%M:%S")
                self.log_print(f"{C.GREEN}📊 NEW POLL DETECTED: {title}{C.RESET}")
                msg_id = self.tg.send_message(poll_text)
                self.active_polls[acc_pubkey] = {'msg_id': msg_id, 'last_total': total_votes, 'is_dashboard': False, 'last_edit': current_time}
            else:
                self.active_polls[acc_pubkey] = {'msg_id': None, 'last_total': total_votes, 'is_dashboard': False, 'last_edit': current_time}
        else:
            last_total = self.active_polls[acc_pubkey]['last_total']
            last_edit_time = self.active_polls[acc_pubkey].get('last_edit', 0)
            is_dashboard = self.active_polls[acc_pubkey].get('is_dashboard', False)
            
            time_elapsed = current_time - last_edit_time
            
            if total_votes != last_total or time_elapsed >= 60:
                if total_votes != last_total:
                    self.log_print(f"{C.YELLOW}Vote change detected! Updating Telegram msg...{C.RESET}")
                
                if is_dashboard:
                    final_text, markup = self.build_dashboard_msg(self.latest_leek, poll_text)
                    self.tg.edit_message(self.active_polls[acc_pubkey]['msg_id'], final_text, markup)
                else:
                    msg_id = self.active_polls[acc_pubkey].get('msg_id')
                    if msg_id:
                        self.tg.edit_message(msg_id, poll_text)
                
                self.active_polls[acc_pubkey]['last_total'] = total_votes
                self.active_polls[acc_pubkey]['last_edit'] = current_time

    def run(self):
        clear()
        print(f"{C.CYAN}🚀 Starting Cyberleek Engine...{C.RESET}")
        print(f"🔄 Syncing blockchain history (silently)...")
        
        self.scan_leaks()
        self.scan_polls()
        
        poll_txt = ""
        if self.latest_poll:
            balances = []
            for i in range(len(self.latest_poll['choices'])):
                addr = self.get_vote_address(self.latest_poll['poll_id'], i)
                balances.append(self.get_token_balance(addr))
            poll_txt = self.format_poll_text(
                self.latest_poll['title'], self.latest_poll['choices'], 
                balances, sum(balances), self.latest_poll['ends_at']
            )

        dash_text, markup = self.build_dashboard_msg(self.latest_leek, poll_txt)
        print("📲 Sending Control Panel to Telegram...")
        msg_id = self.tg.send_message(dash_text, markup)
        
        if self.latest_poll and msg_id:
            pk = self.latest_poll['pubkey']
            if pk in self.active_polls:
                self.active_polls[pk]['msg_id'] = msg_id
                self.active_polls[pk]['is_dashboard'] = True
                self.active_polls[pk]['last_edit'] = time.time()
        
        self.is_first_run = False
        self.log_print(f"{C.GREEN}System online. Tracking {len(self.active_polls)} polls.{C.RESET}")
        
        while True:
            self.draw_dashboard()
            
            if self.scans % 50 == 0:
                self.check_for_updates()
                
            time.sleep(SCAN_INTERVAL) 
            
            self.scan_leaks()
            
            if self.scans % 2 == 0:
                self.scan_polls()
                
            self.scans += 1

if __name__ == "__main__":
    monitor = CyberleekMonitor()
    monitor.run()
