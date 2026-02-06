import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta, timezone
import enum

Base = declarative_base()

# Global offset (in seconds) between system time and network time
_time_offset = 0

def sync_network_time():
    global _time_offset
    try:
        # Using a reliable public HTTP endpoint
        # Baidu is reliable in China
        resp = requests.head("http://www.baidu.com", timeout=3)
        date_str = resp.headers.get('Date')
        if date_str:
            # Parse RFC 2822 date
            # e.g., "Wed, 21 Oct 2015 07:28:00 GMT"
            network_time = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
            network_time = network_time.replace(tzinfo=timezone.utc)
            
            system_time = datetime.utcnow().replace(tzinfo=timezone.utc)
            
            _time_offset = (network_time - system_time).total_seconds()
            print(f"[Zirunbi] Time synced. Offset: {_time_offset:.2f}s")
        else:
            print("[Zirunbi] Failed to get Date header")
    except Exception as e:
        print(f"[Zirunbi] Time sync failed: {e}")

# China Timezone helper with offset
def get_china_time():
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    # Apply offset
    utc_now = utc_now + timedelta(seconds=_time_offset)
    
    cn_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(cn_tz)

class OrderType(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = 'users'
    user_id = Column(String, primary_key=True)
    password_hash = Column(String, nullable=True) # Web login password hash
    balance = Column(Float, default=10000.0)
    # Holdings will be in a separate table
    holdings = relationship("UserHolding", back_populates="user")

class UserHolding(Base):
    __tablename__ = 'user_holdings'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.user_id'))
    symbol = Column(String)
    amount = Column(Float, default=0.0)
    user = relationship("User", back_populates="holdings")

class MarketHistory(Base):
    __tablename__ = 'market_history'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    timestamp = Column(DateTime, default=get_china_time)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class MarketNews(Base):
    __tablename__ = 'market_news'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=get_china_time)
    title = Column(String)
    content = Column(Text)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    symbol = Column(String)
    order_type = Column(Enum(OrderType))
    price = Column(Float, nullable=True) # None for market order
    amount = Column(Float)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    created_at = Column(DateTime, default=get_china_time)

class DB:
    def __init__(self, db_path):
        if not db_path.startswith("sqlite"):
            db_path = f"sqlite:///{db_path}"
        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        
        # Auto-migration for schema updates
        self._migrate()
    
    def _migrate(self):
        with self.engine.connect() as conn:
            # Check and add symbol to orders
            try:
                conn.execute(text("SELECT symbol FROM orders LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN symbol VARCHAR"))
                    conn.commit()
                except Exception as e:
                    print(f"Migration error (orders.symbol): {e}")

            # Check and add symbol to market_history
            try:
                conn.execute(text("SELECT symbol FROM market_history LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE market_history ADD COLUMN symbol VARCHAR"))
                    conn.commit()
                except Exception as e:
                    print(f"Migration error (market_history.symbol): {e}")
            
            # Check and add password_hash to users
            try:
                conn.execute(text("SELECT password_hash FROM users LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
                    conn.commit()
                except Exception as e:
                    print(f"Migration error (users.password_hash): {e}")

        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.Session()
    
    def get_or_create_user(self, user_id):
        session = self.Session()
        user = session.query(User).filter_by(user_id=str(user_id)).first()
        if not user:
            user = User(user_id=str(user_id))
            session.add(user)
            session.commit()
        return user, session
