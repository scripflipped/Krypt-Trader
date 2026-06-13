<div align="center">

<img src="resources/krypt.png" alt="Krypt Trader" width="108" />

# Krypt Trader

**A free, open-source Kalshi auto-trading desktop app.**

Whale tracker, momentum scanner and a configurable trading engine in one clean app — your keys and data never leave your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-6366F1)](LICENSE)
&nbsp;[![Windows 10 | 11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)](#download)
&nbsp;[![Status: beta](https://img.shields.io/badge/status-beta-F59E0B)](#download)
&nbsp;[![Price: free](https://img.shields.io/badge/Price-free-EC4899)](#download)
&nbsp;[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/muzFKR657F)
&nbsp;[![Website](https://img.shields.io/badge/web-krypt.cc-A855F7?logo=googlechrome&logoColor=white)](https://krypt.cc)

</div>

---

Krypt Trader watches the public Kalshi markets for whale orders and momentum, scores them with built-in heuristics, and can size and place trades for you — wrapped in a modern desktop UI instead of a script you have to babysit. Your API keys and every trade stay in a local SQLite database on your machine; the only thing it talks to is Kalshi (and CoinGecko for crypto prices).

> [!WARNING]
> **This app places real orders on your Kalshi account — trading carries real financial risk.** The bundled strategies are heuristics with **no proven, fee-adjusted edge** and may lose money. This is **not financial advice**. It ships on Kalshi's **demo** environment with **dry-run on**, so nothing trades for real until you flip both off. Please read the full [**Disclaimer**](DISCLAIMER.md).

## What it does

- **Whale tracker** — watches the live Kalshi trade feed for big taker orders and surfaces the highest-edge ones in real time.
- **Momentum scanner** — flags volume spikes, price moves and trade clusters, with a contrarian mode that fades the crowd.
- **15-minute crypto** — monitors Kalshi's 15-min BTC, ETH, SOL and other crypto markets with a configurable momentum strategy and an optional paper/live executor.
- **Auto-trader** — sizes positions by edge, places limit-cross orders, tracks fills and resolutions, and reconciles its book against Kalshi on every restart.
- **Profiles & Discord** — save, import and export tuned configs, with optional Discord webhooks and Rich Presence.
- **Local-first** — keys and trade history live under `%APPDATA%/Krypt Trader/`. No account, no telemetry, no middleman server.

## Safe by default

- Starts in **demo + dry-run** — you have to turn both off before a single real order goes out. (The 15-minute crypto tab has its own separate live switch.)
- A **daily stop-loss / take-profit, trading-hours windows and a master kill-switch** gate the engine.
- **Credentials are encrypted at rest** on Windows (DPAPI), tied to your user account — never sent anywhere.
- A **fee-aware backtest** (`npm run py:backtest`) measures the net-of-fee edge on *your own* resolved signals — run it before trusting any preset.

## Download

<a href="../../releases/latest"><img src="https://img.shields.io/badge/Download%20for%20Windows-Krypt%20Trader-A855F7?style=for-the-badge&logo=windows&logoColor=white" alt="Download Krypt Trader" /></a>

Grab the latest installer from the [**Releases**](../../releases/latest) page, run it, then open **API Keys** and connect your Kalshi key + RSA private key. It starts in demo + dry-run, so nothing trades until you turn both off.

> Builds aren't code-signed yet, so the first launch may show a SmartScreen prompt — click **More info → Run anyway**. The full source is right here if you'd rather build it yourself.

## Build from source

```bash
git clone https://github.com/scripflipped/krypt-trader.git
cd krypt-trader
npm install
npm run dev      # auto-creates python/.venv on first run (~30s)
npm run dist     # build the Windows installer into /release
```

Requires [Node.js](https://nodejs.org) 18+ and [Python](https://python.org) 3.10+ on PATH. Development runs on macOS/Linux/Windows; building the packaged installer needs Windows.

## Need a Kalshi account?

Sign up through our referral and Kalshi gives you **$25 free** after your first deposit:
<https://kalshi.com/sign-up?referral=e258d0db-6ca0-4efc-8435-3592397ada4c>

## Links

- **Website** — [krypt.cc](https://krypt.cc) · more free tools at [krypt.cc/tools](https://krypt.cc/tools)
- **Support and community** — [Discord](https://discord.gg/muzFKR657F)
- **Contributing** — see [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Released under the [MIT License](LICENSE) — free to use, fork and share. Please don't rebrand and resell it. Provided **as-is, with no warranty**; see the [Disclaimer](DISCLAIMER.md).

<div align="center"><sub>Built by the Krypt team · <a href="https://krypt.cc">krypt.cc</a></sub></div>
