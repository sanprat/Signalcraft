# Homepage Redesign: Strategy Research & Backtesting Toolkit

## Context

The product direction has shifted from live trading execution to a strategy building, backtesting, and alert generation platform. The homepage must reflect this new positioning as a research toolkit for systematic traders.

## File

`frontend/app/page.tsx` — single-file homepage, same structure, content rewrite only.

---

## Section-by-Section Changes

### 1. Nav Bar (lines 110–178)
- **Keep:** Logo, Sign In, Enter SignalCraft buttons, mobile hamburger
- **Change:** Anchor links from `Products, Features, Infrastructure` → `Products, Features, How It Works`
- Mobile menu links updated accordingly

### 2. Live Ticker Strip (lines 180–213) — REMOVE
- Delete entire ticker section (lines 180–213)
- Adjust content padding-top from `120/160` to `80/110` (nav only, no ticker offset)

### 3. Hero Section (lines 218–304)
- **Badge:** "Next-Gen Algorithmic Trading" → "Strategy Research & Backtesting"
- **Headline:** "Institutional Grade Tools for Independent Traders" → "Build. Backtest. Alert. Trade smarter."
- **Gradient text:** Apply emerald-to-white gradient to "Trade smarter."
- **Subtext:** "Zenalys builds uncompromising automated trading platforms. Backtest flawlessly, execute in milliseconds..." → "Design trading strategies visually, validate them against years of historical data, and get notified when your conditions trigger. No code required."
- **CTA 1:** "Explore SignalCraft" → "Start Building Strategies" (links to /login)
- **CTA 2:** "View Infrastructure" → "See How It Works" (scrolls to #features)

### 4. Stats Section (lines 306–334)
Replace all 4 stats:
- `<10ms Execution Latency` → `16` / `Built-in Indicators`
- `99.9% API Uptime` → `Sub-second` / `Backtest Engine`
- `4 Native Brokers` → `12` / `Stock Screeners`
- `Live Tick By Tick Data` → `Multi-Symbol` / `Strategy Support`

### 5. Product Spotlight: SignalCraft (lines 336–428)
- **Label:** "Flagship Product" stays
- **Description:** Rewrite to focus on strategy building + backtesting + alerts (no mention of live execution)
- **Bullet points:**
  1. "Visual No-Code Strategy Builder" → keep
  2. "TradingView-style interactive chart replay" → keep
  3. "Nifty, BankNifty, & FinNifty Options Support" → keep
  4. "Direct execution via Dhan, Zerodha, Shoonya" → **replace** with "Condition-Based Alert Notifications"
- **CTA:** "Open SignalCraft App" stays

### 6. Features Grid (lines 430–486)
Replace all 6 feature cards:

| # | Old | New Icon | New Title | New Description |
|---|-----|----------|-----------|-----------------|
| 1 | Low Latency Execution | 🧩 | Visual Strategy Builder | Drag-and-drop entry and exit conditions with 16 indicators, 8 operators, and ALL/ANY logic. Build complex strategies without writing code. |
| 2 | Encrypted Credential Vault | 📊 | Multi-Indicator Engine | RSI, SMA, EMA, MACD, Supertrend, Bollinger Bands, ATR, ADX, and more. Stack and combine indicators with configurable parameters. |
| 3 | Resilient Order Management | 📈 | Historical Replay & Charting | Interactive candlestick charts with trade annotations. Replay your strategy's decisions on years of NIFTY500 and FnO data. |
| 4 | High-Fidelity Data | 🧪 | Backtest Analytics | Detailed PnL reports with win rate, max drawdown, equity curves, per-symbol breakdowns, and full trade logs. |
| 5 | Risk Guardrails | 🔔 | Condition-Based Alerts | Set up alerts when indicators cross thresholds, price hits levels, or custom conditions trigger. Get notified via Telegram instantly. |
| 6 | Multi-Broker Accounts | 🔍 | Stock Screeners | 12 built-in screeners — Minervini, VCP, IBD CAN SLIM, RSI Momentum, MACD Crossover, and more. Filter NIFTY500 in seconds. |

### 7. Footer CTA (lines 488–522)
- **Headline:** "Ready to trade programmatically?" → "Ready to validate your edge?"
- **Subtext:** "Join the beta of SignalCraft today. Connect your broker and deploy your first algorithmic strategy in minutes." → "Build strategies, backtest against historical data, and get alerts when your conditions trigger. Start for free today."
- **CTA button:** "Start Deploying" → "Start Building"

### 8. Footer (lines 524–547)
- No changes

---

## Imports Cleanup
- Remove `useQuotes` import (line 5) since ticker is removed
- Remove `quotes, connected, isLive, marketOpen` destructuring from useQuotes() (line 81)
- Remove `LiveDot` component (lines 28–32) since ticker is removed

## Out of Scope
- No new components or routes
- No CSS/styling changes (colors, layout, responsive behavior stay the same)
- No backend changes
- Alert feature "coming soon" badge — not adding for now, keeping it as a present capability

## Validation
- Screenshot before and after with Playwright
- Check mobile viewport (375px) and desktop (1280px)
- Verify all anchor links scroll to correct sections
- Verify Sign In / Enter SignalCraft buttons still link to /login
