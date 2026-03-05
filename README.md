# SignalCraft (Pytrader) 🚀

<a href="https://www.zenalys.com" target="_blank">www.zenalys.com</a>

![SignalCraft Banner](https://raw.githubusercontent.com/sanprat/Signalcraft/main/images/admin.png)

**SignalCraft** is a sophisticated, real-time algorithmic trading and market analysis platform. Built with a focus on speed, reliability, and precision, it empowers traders to automate strategies, monitor global markets, and perform deep historical analysis with ease.

---

## ✨ Features

- **⚡ Real-time Market Data**: Direct integration with Dhan WebSocket for sub-second quote updates.
- **📊 Advanced Charting**: Integrated TradingView Lightweight Charts for high-performance visualization.
- **🤖 Strategy Engine**: Multi-threaded backend for deploying and monitoring algorithmic strategies.
- **🛡️ Risk Management**: Built-in position management, P&L tracking, and safety protocols.
- **📈 Global Screeners**: 12+ pre-configured screeners, including Minervini Trend Template and custom RSI indicators.
- **🗄️ Historical Data**: Optimized Parquet-based storage for lightning-fast backtesting on years of stock data.
- **📱 Responsive Dashboard**: Premium React-based UI for a seamless experience across desktop and mobile.

---

## 🛠️ Tech Stack

- **Frontend**: [Next.js](https://nextjs.org/), [React](https://reactjs.org/), [Tailwind CSS](https://tailwindcss.com/)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Data Layer**: [Pandas](https://pandas.pydata.org/), [PyArrow](https://arrow.apache.org/docs/python/) (Parquet), [Redis](https://redis.io/)
- **Infrastructure**: [Docker](https://www.docker.com/), [PostgreSQL](https://www.postgresql.org/)
- **Data Providers**: [Dhan API](https://dhan.co/), [YFinance](https://github.com/ranaroussi/yfinance)

---

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- Dhan API Credentials (Client ID, Access Token)

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sanprat/Signalcraft.git
   cd Signalcraft
   ```

2. **Set up Environment Variables**:
   Create a `.env` file in the root directory (refer to `.env.local.example` in frontend/backend):
   ```env
   DHAN_CLIENT_ID=your_id
   DHAN_ACCESS_TOKEN=your_token
   ```

3. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**:
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000/docs`

---

## 📂 Project Structure

```
├── backend/            # FastAPI application logic
│   ├── app/            # Core modules, routers, and models
│   └── strategies/     # Stored algorithmic strategies
├── frontend/           # Next.js application
│   ├── app/            # Pages and layouts
│   └── components/     # UI components
├── data-scripts/       # Utilities for data download and management
└── docker-compose.yml  # Orchestration for the full stack
```

---

## 📝 License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**. 

- **Attribution**: You must give appropriate credit.
- **Non-Commercial**: You may not use the material for commercial purposes without explicit permission.

See [LICENSE](LICENSE) for full details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

*Built with ❤️ by [sanprat](https://github.com/sanprat)*
