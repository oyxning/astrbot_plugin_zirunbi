from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from typing import List, Optional
import uvicorn
import asyncio
import os

from .database import DB, User, UserHolding, Order, OrderType, OrderStatus, MarketHistory, get_china_time
from .market import Market

# Password hashing
# Use pbkdf2_sha256 to avoid bcrypt 72-byte limit/version issues on Windows
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI()

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "web")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Dependency
def get_db():
    # This is a bit tricky since DB is initialized in main.py
    # We will inject DB instance into app state
    db = app.state.db_instance
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()

class LoginModel(BaseModel):
    user_id: str
    password: str

class TradeModel(BaseModel):
    user_id: str
    symbol: str
    amount: float
    price: Optional[float] = None
    action: str # "buy" or "sell"

@app.post("/api/login")
async def login(data: LoginModel, session: Session = Depends(get_db)):
    user = session.query(User).filter_by(user_id=data.user_id).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="User not found or password not set")
    
    if not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    return {"status": "success", "user_id": user.user_id, "balance": user.balance}

@app.get("/api/market")
async def get_market_data():
    market: Market = app.state.market_instance
    prices = market.prices
    # Calculate changes (simplified)
    # Ideally reuse logic from main.py /zrb change, but for now just send current prices
    return {"prices": prices, "is_open": market.is_open}

@app.get("/api/assets/{user_id}")
async def get_assets(user_id: str, session: Session = Depends(get_db)):
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    holdings = session.query(UserHolding).filter_by(user_id=user_id).all()
    holdings_list = []
    for h in holdings:
        if h.amount > 0.0001:
            holdings_list.append({"symbol": h.symbol, "amount": h.amount})
            
    return {"balance": user.balance, "holdings": holdings_list}

@app.post("/api/trade")
async def trade(data: TradeModel, session: Session = Depends(get_db)):
    market: Market = app.state.market_instance
    
    if not market.is_open:
         raise HTTPException(status_code=400, detail="Market is closed")

    user = session.query(User).filter_by(user_id=data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    symbol = data.symbol.upper()
    if symbol not in market.symbols:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Basic Validation
    if data.action == "buy":
        est_price = data.price if data.price else market.prices[symbol]
        cost = est_price * data.amount * 1.001
        if user.balance < cost:
            raise HTTPException(status_code=400, detail=f"Insufficient balance. Need {cost:.2f}")
    elif data.action == "sell":
        holding = session.query(UserHolding).filter_by(user_id=data.user_id, symbol=symbol).first()
        if not holding or holding.amount < data.amount:
             raise HTTPException(status_code=400, detail=f"Insufficient holding")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Create Order
    order_type = OrderType.BUY if data.action == "buy" else OrderType.SELL
    order = Order(
        user_id=data.user_id,
        symbol=symbol,
        order_type=order_type,
        price=data.price,
        amount=data.amount
    )
    session.add(order)
    session.commit()
    order_id = order.id
    
    # Trigger Match
    market.match_single_order(order_id)
    
    # Check Result
    session.refresh(order)
    return {
        "status": "success", 
        "order_id": order_id, 
        "order_status": order.status.value,
        "message": "Order submitted"
    }

@app.get("/api/kline/{symbol}")
async def get_kline(symbol: str, session: Session = Depends(get_db)):
    symbol = symbol.upper()
    # Get last 100 records
    history = session.query(MarketHistory).filter_by(symbol=symbol).order_by(MarketHistory.timestamp.desc()).limit(100).all()
    
    # Reverse to chronological order
    history = history[::-1]
    
    data = []
    for h in history:
        data.append({
            "time": h.timestamp.strftime('%Y-%m-%d %H:%M'),
            "open": h.open,
            "high": h.high,
            "low": h.low,
            "close": h.close,
            "volume": h.volume
        })
    return {"symbol": symbol, "data": data}

@app.get("/")
async def index():
    with open(os.path.join(static_path, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

import socket
import logging

logger = logging.getLogger("astrbot")

class WebServer:
    def __init__(self, db: DB, market: Market, host="0.0.0.0", port=8000):
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)
        self.host = host
        self.port = port
        
        # Inject instances
        app.state.db_instance = db
        app.state.market_instance = market

    def is_port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # 0 means connected successfully, i.e., port is in use
                return s.connect_ex(('localhost', self.port)) == 0
            except:
                return False

    async def start(self):
        # Pre-check port
        if self.is_port_in_use():
            logger.error(f"[Zirunbi] Web Server Error: Port {self.port} is already in use!")
            logger.error(f"[Zirunbi] Please change 'web_port' in plugin config or close the application using this port.")
            return

        try:
            await self.server.serve()
        except BaseException as e:
            # Catch SystemExit and others
            if isinstance(e, SystemExit):
                logger.warning(f"[Zirunbi] Web Server stopped (SystemExit).")
            else:
                logger.error(f"[Zirunbi] Web Server runtime error: {e}")

    async def stop(self):
        self.server.should_exit = True
    
    def run_in_background(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.start())
