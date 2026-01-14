import threading
import time
import random
from datetime import datetime, timedelta, timezone
try:
    from .database import DB, User, UserHolding, Order, OrderType, OrderStatus, MarketHistory, MarketNews, get_china_time, sync_network_time
except ImportError:
    from database import DB, User, UserHolding, Order, OrderType, OrderStatus, MarketHistory, MarketNews, get_china_time, sync_network_time

class Market:
    def __init__(self, db: DB, config: dict):
        self.db = db
        self.config = config
        self.volatility = float(config.get("volatility", 0.02))
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Sync network time
        sync_network_time()
        
        # Market State Logic
        # True = Open, False = Closed
        self.is_open = False 
        self.manual_override = None # None: Auto, True/False: Manual
        self.last_auto_state = None # To track transitions
        
        # Define symbols
        self.symbols = ["ZRB", "STAR", "SHEEP", "XIANGZI", "MIAO"]
        
        # Initial prices
        self.prices = {
            "ZRB": float(config.get("initial_price", 100.0)),
            "STAR": 50.0,
            "SHEEP": 10.0,
            "XIANGZI": 5.0,
            "MIAO": 20.0
        }
        
        # Current candles per symbol
        self.current_candles = {}
        now = get_china_time()
        for sym in self.symbols:
            self.current_candles[sym] = {
                "open": self.prices[sym],
                "high": self.prices[sym],
                "low": self.prices[sym],
                "close": self.prices[sym],
                "volume": 0.0,
                "start_time": now
            }
        
        # Load last prices from DB
        self._load_history()
        
        # Update interval
        self.last_update_time = time.time()
        self.update_interval = 180 # 3 minutes
        
        # News Templates
        self.news_templates = [
            "{symbol} 宣布与神秘财团达成战略合作，市场情绪高涨！",
            "据传 {symbol} 创始团队正在大量抛售，引发市场恐慌。",
            "业内分析师指出 {symbol} 技术面出现金叉，未来可期。",
            "监管部门对 {symbol} 展开反垄断调查，前景不明。",
            "{symbol} 社区发起销毁提案，通缩预期增强。",
            "著名投资人 LumineStory 公开看好 {symbol}，称其为下一个百倍币。",
            "黑客攻击导致 {symbol} 链上交易拥堵，用户体验下降。",
            "{symbol} 发布重磅更新路线图，包含元宇宙生态布局。",
            "受宏观经济影响，资金正在撤离 {symbol} 板块。",
            "{symbol} 获得顶级风投机构千万级美元融资。",
            "某知名交易所暗示即将上线 {symbol}，引发抢筹热潮。",
            "{symbol} 首席执行官在社交媒体发布神秘代码，社区猜测是重大利好。",
            "由于节点升级失败，{symbol} 网络暂停出块 1 小时。",
            "第三方安全机构完成对 {symbol} 的审计，评分高于预期。",
            "{symbol} 宣布进军 AI 算力领域，试图蹭上热点。",
            "链上数据显示，某巨鲸地址刚刚转入 1000 万枚 {symbol}。",
            "{symbol} 官方 Discord 频道遭黑客入侵，发布虚假钓鱼链接。",
            "受美联储加息预期影响，{symbol} 跟随大盘跳水。",
            "{symbol} 推出质押挖矿活动，年化收益率高达 500%。",
            "竞争对手爆出丑闻，资金回流至 {symbol}。",
            "{symbol} 核心开发者宣布离职，引发社区对项目前景的担忧。",
            "神秘买家以溢价 20% 场外收购大量 {symbol}。",
            "{symbol} 将与知名游戏工作室合作开发链游。",
            "监管机构澄清 {symbol} 不属于证券，合规风险解除。",
            "{symbol} 粉丝见面会现场火爆，信仰充值成功。"
        ]

    def _load_history(self):
        try:
            session = self.db.get_session()
            for sym in self.symbols:
                last = session.query(MarketHistory).filter_by(symbol=sym).order_by(MarketHistory.timestamp.desc()).first()
                if last:
                    self.prices[sym] = last.close
                    self.current_candles[sym]["open"] = last.close
                    self.current_candles[sym]["high"] = last.close
                    self.current_candles[sym]["low"] = last.close
                    self.current_candles[sym]["close"] = last.close
            session.close()
        except Exception as e:
            print(f"Error loading history: {e}")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def set_open(self, is_open: bool):
        """Admin override"""
        self.manual_override = is_open
        self.is_open = is_open

    def _check_market_hours(self):
        """
        Check if market should be open based on real China time.
        Trading Hours:
          09:30 - 11:30
          13:00 - 15:00
        Closed on Weekends (Saturday=5, Sunday=6)
        """
        now = get_china_time()
        
        # Weekends closed
        if now.weekday() >= 5:
            return False
            
        current_time = now.time()
        
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()
        
        is_trading_time = (morning_start <= current_time <= morning_end) or \
                          (afternoon_start <= current_time <= afternoon_end)
                          
        return is_trading_time

    def get_status_info(self):
        now = get_china_time()
        is_weekend = now.weekday() >= 5
        
        # Schedule definition
        morning_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        morning_end = now.replace(hour=11, minute=30, second=0, microsecond=0)
        afternoon_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
        afternoon_end = now.replace(hour=15, minute=0, second=0, microsecond=0)
        
        status_str = ""
        countdown_str = ""
        
        if is_weekend:
            status_str = "周末休市"
            # Calculate days until Monday 9:30
            days_until_mon = 7 - now.weekday()
            next_open = morning_start + timedelta(days=days_until_mon)
            delta = next_open - now
            countdown_str = f"距离开市还有: {delta.days}天 {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
        else:
            if now < morning_start:
                status_str = "早盘未开"
                delta = morning_start - now
                countdown_str = f"距离早盘开市: {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
            elif morning_start <= now <= morning_end:
                status_str = "早盘交易中"
                delta = morning_end - now
                countdown_str = f"距离午间休市: {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
            elif morning_end < now < afternoon_start:
                status_str = "午间休市"
                delta = afternoon_start - now
                countdown_str = f"距离午盘开市: {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
            elif afternoon_start <= now <= afternoon_end:
                status_str = "午盘交易中"
                delta = afternoon_end - now
                countdown_str = f"距离今日收盘: {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
            else:
                status_str = "今日已收盘"
                # Next day 9:30
                next_open = morning_start + timedelta(days=1)
                # Skip weekend if Friday
                if now.weekday() == 4: # Friday
                    next_open += timedelta(days=2)
                delta = next_open - now
                countdown_str = f"距离下个交易日开市: {delta.days}天 {delta.seconds//3600}小时 {(delta.seconds//60)%60}分"
                
        return {
            "now_str": now.strftime("%Y-%m-%d %H:%M:%S (UTC+8)"),
            "status": status_str,
            "countdown": countdown_str,
            "schedule": "周一至周五 09:30-11:30, 13:00-15:00"
        }

    def _loop(self):
        while self.running:
            try:
                # --- Auto Open/Close Logic ---
                should_be_open = self._check_market_hours()
                
                # If this is the first run, initialize last_auto_state
                if self.last_auto_state is None:
                    self.last_auto_state = should_be_open
                    # Initial state (if no manual override yet)
                    if self.manual_override is None:
                        self.is_open = should_be_open
                
                # Check for state transition
                if should_be_open != self.last_auto_state:
                    # Transition occurred!
                    # Auto logic takes precedence, clearing manual override
                    self.manual_override = None 
                    self.is_open = should_be_open
                    self.last_auto_state = should_be_open
                    print(f"[Zirunbi] Market state auto-transition to: {'OPEN' if should_be_open else 'CLOSED'}")
                    
                    # If market just opened, trigger match orders immediately
                    if self.is_open:
                        self.match_orders()
                
                # Apply manual override if active, otherwise follow auto schedule
                if self.manual_override is not None:
                    self.is_open = self.manual_override
                # else: self.is_open is already set by transitions or init
                
                if not self.is_open:
                    time.sleep(1)
                    continue

                now_ts = time.time()
                if now_ts - self.last_update_time >= self.update_interval:
                    self.last_update_time = now_ts
                    self._update_prices()
                    self._save_candles()
                    self._generate_news() # Generate news
                    # Trigger match orders after price update (for Limit orders)
                    self.match_orders()
                
                time.sleep(1)
            except Exception as e:
                print(f"Market loop error: {e}")
                time.sleep(5)

    def _generate_news(self):
        # 30% chance to generate news per update cycle
        if random.random() < 0.3:
            try:
                symbol = random.choice(self.symbols)
                template = random.choice(self.news_templates)
                content = template.format(symbol=symbol)
                
                session = self.db.get_session()
                news = MarketNews(
                    title=f"关于 {symbol} 的市场快讯",
                    content=content
                )
                session.add(news)
                session.commit()
                session.close()
            except Exception as e:
                print(f"Generate news error: {e}")

    def _update_prices(self):
        with self.lock:
            for sym in self.symbols:
                price = self.prices[sym]
                change_pct = random.gauss(0, self.volatility)
                price *= (1 + change_pct)
                price = max(0.01, price)
                self.prices[sym] = price
                
                # Update candle
                candle = self.current_candles[sym]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price

    def _save_candles(self):
        with self.lock:
            session = self.db.get_session()
            now = get_china_time()
            for sym in self.symbols:
                candle = self.current_candles[sym]
                history = MarketHistory(
                    symbol=sym,
                    timestamp=candle["start_time"], # Use the start time of the period
                    open=candle["open"],
                    high=candle["high"],
                    low=candle["low"],
                    close=candle["close"],
                    volume=candle["volume"]
                )
                session.add(history)
                
                # Reset candle for next period
                self.current_candles[sym] = {
                    "open": self.prices[sym],
                    "high": self.prices[sym],
                    "low": self.prices[sym],
                    "close": self.prices[sym],
                    "volume": 0.0,
                    "start_time": now
                }
            session.commit()
            session.close()

    def match_single_order(self, order_id):
        """Try to match a specific order immediately (for immediate feedback)"""
        session = self.db.get_session()
        order = session.query(Order).filter_by(id=order_id, status=OrderStatus.PENDING).first()
        if order:
            self._process_order(session, order)
        session.commit()
        session.close()

    def match_orders(self):
        """Match all pending orders"""
        session = self.db.get_session()
        orders = session.query(Order).filter(Order.status == OrderStatus.PENDING).all()
        for order in orders:
            self._process_order(session, order)
        session.commit()
        session.close()

    def _process_order(self, session, order):
        if not self.is_open:
            return

        current_price = self.prices.get(order.symbol)
        if not current_price:
            return

        execute = False
        exec_price = current_price
        
        if order.price is None: # Market order
            execute = True
        elif order.order_type == OrderType.BUY and current_price <= order.price:
            execute = True
        elif order.order_type == OrderType.SELL and current_price >= order.price:
            execute = True
        
        if execute:
            self._execute_order(session, order, exec_price)

    def _execute_order(self, session, order, exec_price):
        user = session.query(User).filter_by(user_id=order.user_id).first()
        if not user:
            return
            
        fee_rate = 0.001
        total_cost = exec_price * order.amount
        fee = total_cost * fee_rate
        
        if order.order_type == OrderType.BUY:
            cost_with_fee = total_cost + fee
            if user.balance >= cost_with_fee:
                user.balance -= cost_with_fee
                # Update holding
                holding = session.query(UserHolding).filter_by(user_id=user.user_id, symbol=order.symbol).first()
                if not holding:
                    holding = UserHolding(user_id=user.user_id, symbol=order.symbol, amount=0.0)
                    session.add(holding)
                holding.amount += order.amount
                
                order.status = OrderStatus.FILLED
                with self.lock:
                    if order.symbol in self.current_candles:
                        self.current_candles[order.symbol]["volume"] += order.amount
            else:
                order.status = OrderStatus.CANCELLED # Cancel if insufficient funds at execution
        
        elif order.order_type == OrderType.SELL:
            holding = session.query(UserHolding).filter_by(user_id=user.user_id, symbol=order.symbol).first()
            if holding and holding.amount >= order.amount:
                holding.amount -= order.amount
                revenue = total_cost - fee
                user.balance += revenue
                
                order.status = OrderStatus.FILLED
                with self.lock:
                     if order.symbol in self.current_candles:
                        self.current_candles[order.symbol]["volume"] += order.amount
            else:
                order.status = OrderStatus.CANCELLED
