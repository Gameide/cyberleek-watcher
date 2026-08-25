# ⚡ Cyberleek On-Chain Monitor & Telegram Bot

A lightweight, high-performance monitoring tool that interacts directly with the **Solana Mainnet RPC**. It tracks new Cyberleek content releases and monitors live on-chain voting polls in real time without relying on web scrapers or third-party frontends.

---
Based on https://github.com/FermataRest/cyberleek-leak-research (Solana Feature)
Credits to: Gemini (Yes, Gemini did build all this alone)

## 🚀 Key Features

* **Direct Solana RPC Integration:** Queries on-chain program accounts directly (`getProgramAccounts`) with zero website or browser dependency.
* **Instant Telegram Alerts:** Sends notifications with interactive mirror links as soon as a new post is confirmed on the blockchain.
* **Media Auto-Download:** Automatically downloads and attaches media files (under 50 MB) directly to the Telegram message. (only for aerwave.net, temp.sh files)
* **Live Poll Dashboard:** Displays live voting tallies and dynamically edits the Telegram message as new votes arrive.
* **Built-in Terminal Dashboard:** Color-coded CLI interface displaying real-time uptime, scan count, RPC status, and activity logs.
* **Update Notification System:** Checks GitHub periodically for new script versions and alerts the user when an update is available.

---

## 📋 Prerequisites

* Python 3.9+
* A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
* Your Telegram Chat ID (from [@id_bot](https://t.me/id_bot))

---

##  Disclaimer

- **No Affiliation**: This project and its author are not affiliated,
  associated, authorized, endorsed by, or in any way officially connected with
  Rockstar Games, Take-Two Interactive, Cyberleek, or any of their subsidiaries
  or affiliates.
- **Educational & Research Purposes Only**: This is an independent viewer
  provided solely for educational research into decentralized publishing
  patterns; it only reads public on-chain data.
- **Content Responsibility**: The author does not host, stream, generate, or
  claim ownership of any third-party media, leaked content, or intellectual
  property. All product names, logos, brands, and media mentioned or displayed
  belong to their respective copyright holders.
- **Use at Your Own Risk**: Software is provided "as is", without warranty of
  any kind. You are solely responsible for ensuring compliance with your local
  laws and host provider terms of service.

