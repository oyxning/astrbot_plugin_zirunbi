from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.all import *
import os
import io
import tempfile

try:
    from .database import DB, Order, OrderType, OrderStatus, MarketHistory, UserHolding, MarketNews, get_china_time
    from .market import Market
    from . import plotter
except ImportError:
    from database import DB, Order, OrderType, OrderStatus, MarketHistory, UserHolding, MarketNews, get_china_time
    from market import Market
    import plotter

from datetime import datetime, timedelta

@register("zrb_trader", "LumineStory", "模拟炒股插件", "1.0.2", "https://github.com/oyxning/astrbot-plugin-zirunbi")
class ZRBTrader(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.db_path = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'zirunbi.db')}"
        self.db = DB(self.db_path)
        self.market = Market(self.db, config)
        self.market.start()

    def terminate(self):
        self.market.stop()

    def _save_temp_image(self, buf):
        """Helper to save BytesIO to temp file for image_result"""
        try:
            fd, path = tempfile.mkstemp(suffix=".png")
            with os.fdopen(fd, 'wb') as f:
                f.write(buf.getvalue())
            return path
        except Exception as e:
            logger.error(f"Save temp image error: {e}")
            return None

    @filter.command("zrb")
    async def zrb(self, event: AstrMessageEvent):
        """模拟炒股指令"""
        args = event.message_str.split()
        if len(args) < 2:
            help_text = """【模拟炒股交易助手】
📈 市场行情
/zrb price [币种] - 查看实时价格
/zrb kline <币种> - 查看近期K线 (60点)
/zrb history <币种> [天数] - 查看历史K线
/zrb time - 查看股市交易时间表
/zrb info [币种] - 查看币种介绍
/zrb news - 查看今日市场快讯

💰 交易指令
/zrb buy <币种> <数量> [限价] - 买入 (不填价格为市价单)
/zrb sell <币种> <数量> [限价] - 卖出
/zrb orders - 查看未成交挂单
/zrb cancel <ID> - 撤销指定挂单
/zrb assets - 查看我的资产与持仓
/zrb today - 查看今日交易日报

🔧 管理/其他
/zrb reset - 重置我的账户
/zrb admin open/close - 管理员开关市

🪙 支持币种
ZRB(孜然), STAR(星星), SHEEP(小羊), XIANGZI(祥子), MIAO(喵喵)"""
            yield event.plain_result(help_text)
            return

        cmd = args[1]
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        # Admin check helper
        def is_admin():
            return user_id in self.config.get("admin_ids", [])

        if cmd == "price":
            # /zrb price [symbol]
            msg = "【当前市场价格】\n"
            if len(args) > 2:
                sym = args[2].upper()
                if sym in self.market.prices:
                     msg += f"{sym}: {self.market.prices[sym]:.2f}\n"
                else:
                    msg += f"未知币种: {sym}"
            else:
                for sym, price in self.market.prices.items():
                    msg += f"{sym}: {price:.2f}\n"
            yield event.plain_result(msg)
            
        elif cmd == "kline":
            # /zrb kline <symbol>
            if len(args) < 3:
                yield event.plain_result("请输入币种，例如: /zrb kline ZRB")
                return
            sym = args[2].upper()
            if sym not in self.market.symbols:
                yield event.plain_result(f"不支持的币种: {sym}")
                return

            if not self.market.is_open:
                yield event.plain_result(f"当前市场休市中，价格未变动。\n您可以查看截止休市前的K线。")
                
            session = self.db.get_session()
            history = session.query(MarketHistory).filter_by(symbol=sym).order_by(MarketHistory.timestamp.desc()).limit(60).all()
            session.close()
            
            # Reverse back to chronological order
            history = history[::-1]
            
            if not history:
                yield event.plain_result(f"暂无 {sym} 历史数据")
                return
                
            title_suffix = " (Closed)" if not self.market.is_open else ""
            img_buf = plotter.plot_kline(history, title=f"{sym} Recent K-Line{title_suffix}")
            if img_buf:
                img_path = self._save_temp_image(img_buf)
                if img_path:
                    yield event.image_result(img_path)
                else:
                    yield event.plain_result("绘图保存失败")
            else:
                yield event.plain_result("绘图失败")

        elif cmd == "history":
            # /zrb history <symbol> [days]
            if len(args) < 3:
                yield event.plain_result("请输入币种，例如: /zrb history ZRB")
                return
            
            sym = args[2].upper()
            if sym not in self.market.symbols:
                yield event.plain_result(f"不支持的币种: {sym}")
                return
            
            days = 3
            if len(args) > 3:
                try:
                    days = int(args[3])
                    days = max(1, min(days, 30)) # Limit 1 to 30 days
                except ValueError:
                    pass
            
            session = self.db.get_session()
            now = get_china_time()
            start_date = now - timedelta(days=days)
            
            history = session.query(MarketHistory).filter(
                MarketHistory.symbol == sym,
                MarketHistory.timestamp >= start_date
            ).order_by(MarketHistory.timestamp).all()
            session.close()
            
            if not history:
                yield event.plain_result(f"当日无数据")
                return
            
            # If too many points, resample might be needed, but for now just plot all (mpf handles reasonable amount)
            # If > 500 points, maybe limit? 3 mins * 4 hours * days = 80 points/day. 3 days = 240. 30 days = 2400.
            # mpf can handle 2400 but might be crowded. Let's limit display logic if needed later.
            
            img_buf = plotter.plot_kline(history, title=f"{sym} History ({days} Days)")
            if img_buf:
                img_path = self._save_temp_image(img_buf)
                if img_path:
                    yield event.image_result(img_path)
                else:
                    yield event.plain_result("绘图保存失败")
            else:
                yield event.plain_result("绘图失败")

        elif cmd == "news":
            # /zrb news
            session = self.db.get_session()
            # Only show news from today
            now = get_china_time()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            news_list = session.query(MarketNews).filter(
                MarketNews.timestamp >= today_start
            ).order_by(MarketNews.timestamp.desc()).limit(10).all()
            session.close()
            
            if not news_list:
                yield event.plain_result("今日暂无市场新闻。")
                return
            
            msg = f"【今日市场快讯 ({now.strftime('%m-%d')})】\n"
            for n in news_list:
                t_str = n.timestamp.strftime("%H:%M")
                msg += f"[{t_str}] {n.content}\n"
            yield event.plain_result(msg)

        elif cmd == "today":
            # /zrb today
            session = self.db.get_session()
            now = get_china_time()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            orders = session.query(Order).filter(
                Order.user_id == user_id,
                Order.status == OrderStatus.FILLED,
                Order.created_at >= today_start
            ).all()
            session.close()
            
            msg = f"【今日交易日报】\n📅 {now.strftime('%Y-%m-%d')}\n\n"
            
            if not orders:
                msg += "今日无交易记录。\n"
            else:
                buy_stats = {} # {symbol: {count, total_amt, total_cost}}
                sell_stats = {}
                
                for o in orders:
                    stats = buy_stats if o.order_type == OrderType.BUY else sell_stats
                    if o.symbol not in stats:
                        stats[o.symbol] = {'count': 0, 'amt': 0.0, 'cost': 0.0}
                    
                    stats[o.symbol]['count'] += 1
                    stats[o.symbol]['amt'] += o.amount
                    # For filled orders, price should be set. If None (market order), we approximate or skip cost calc if not recorded. 
                    # Note: In real system, we should record execution price. Currently Order.price is limit price. 
                    # Simplified: use Order.price if set, else approximate with current price (inaccurate).
                    # Better: Market logic should update Order.price to execution price upon fill. 
                    # Assuming Market logic updates price or we accept limit price as approximation.
                    # Actually market.py doesn't update order.price to execution price for market orders. 
                    # It uses current price. Let's just show amount.
                    
                msg += "💰 交易统计:\n"
                if buy_stats:
                    msg += "  [买入]\n"
                    for sym, data in buy_stats.items():
                        msg += f"  - {sym}: {data['amt']:.2f}个 ({data['count']}笔)\n"
                if sell_stats:
                    msg += "  [卖出]\n"
                    for sym, data in sell_stats.items():
                        msg += f"  - {sym}: {data['amt']:.2f}个 ({data['count']}笔)\n"
            
            msg += "\n📈 即时币价:\n"
            for sym, price in self.market.prices.items():
                msg += f"{sym}: {price:.2f}\n"
                
            yield event.plain_result(msg)

        elif cmd == "time":
            # /zrb time
            info = self.market.get_status_info()
            msg = f"""【股市时间表】
当前时间: {info['now_str']}
市场状态: {info['status']}
{info['countdown']}

📅 交易时段:
{info['schedule']}"""
            yield event.plain_result(msg)

        elif cmd == "info":
            # /zrb info [symbol]
            coin_info = {
                "ZRB": "【孜然币 (Ziran Coin)】\n代号: ZRB\n本插件的基础货币，象征着烤肉的灵魂。据说每一枚孜然币都散发着诱人的香气。\n(虚拟资产，仅供娱乐)",
                "STAR": "【星星币 (Star Coin)】\n代号: STAR\n来自遥远星系的神秘货币，闪烁着希望的光芒。持有者相信它能带领大家飞向月球。\n(虚拟资产，仅供娱乐)",
                "SHEEP": "【小羊币 (Sheep Coin)】\n代号: SHEEP\n温顺可爱的小羊，但在市场波动时可能会变成猛兽。社区共识极强。\n(虚拟资产，仅供娱乐)",
                "XIANGZI": "【祥子币 (Xiangzi Coin)】\n代号: XIANGZI\n为了纪念努力奋斗的祥子而发行。象征着坚韧不拔的打工人精神。\n(虚拟资产，仅供娱乐)",
                "MIAO": "【喵喵币 (Miao Coin)】\n代号: MIAO\n由神秘的猫咪组织发行，充满变数与灵动。据说只有被选中的铲屎官才能驾驭。\n(虚拟资产，仅供娱乐)"
            }
            
            if len(args) > 2:
                sym = args[2].upper()
                if sym in coin_info:
                    yield event.plain_result(coin_info[sym])
                else:
                    if sym in self.market.symbols:
                         yield event.plain_result(f"【{sym}】\n暂无详细介绍。\n(虚拟资产，仅供娱乐)")
                    else:
                        yield event.plain_result(f"未知币种: {sym}")
            else:
                msg = "【币种介绍大全 (虚拟资产)】\n\n"
                for code, desc in coin_info.items():
                    msg += f"{desc}\n{'-'*20}\n"
                yield event.plain_result(msg)

        elif cmd == "buy" or cmd == "sell":
            # /zrb buy <symbol> <amount> [price]
            if len(args) < 4:
                yield event.plain_result(f"格式错误。示例: /zrb {cmd} ZRB 100")
                return
            
            symbol = args[2].upper()
            if symbol not in self.market.symbols:
                yield event.plain_result(f"不支持的币种: {symbol}")
                return
                
            try:
                amount = float(args[3])
                price = float(args[4]) if len(args) > 4 else None
            except ValueError:
                yield event.plain_result("数量或价格必须是数字")
                return

            if amount <= 0:
                yield event.plain_result("数量必须大于0")
                return

            user, session = self.db.get_or_create_user(user_id)
            
            # Basic validation
            if cmd == "buy":
                est_price = price if price else self.market.prices[symbol]
                cost = est_price * amount * 1.001 # +0.1% fee
                if user.balance < cost:
                    session.close()
                    yield event.plain_result(f"余额不足。预估需要 {cost:.2f}, 当前余额 {user.balance:.2f}")
                    return
            else: # sell
                # Check holding
                holding = session.query(UserHolding).filter_by(user_id=user_id, symbol=symbol).first()
                if not holding or holding.amount < amount:
                    session.close()
                    yield event.plain_result(f"持仓不足。当前持有 {holding.amount if holding else 0} {symbol}")
                    return

            order_type = OrderType.BUY if cmd == "buy" else OrderType.SELL
            order = Order(
                user_id=user_id,
                symbol=symbol,
                order_type=order_type,
                price=price,
                amount=amount
            )
            session.add(order)
            session.commit()
            order_id = order.id
            session.close()
            
            # Trigger immediate match
            self.market.match_single_order(order_id)
            
            # Check status
            session = self.db.get_session()
            updated_order = session.query(Order).get(order_id)
            
            if updated_order.status == OrderStatus.FILLED:
                status_msg = "✅ 已成交"
                desc = f"成交价格: {self.market.prices[symbol]:.2f}"
            else:
                if not self.market.is_open:
                    status_msg = "🕒 已挂单 (休市中)"
                    desc = "市场休市中，订单已挂起，将在开盘后自动撮合。"
                else:
                    status_msg = "⏱️ 已挂单"
                    desc = "订单已提交，等待市场价格到达指定价位。"
            
            session.close()

            yield event.plain_result(f"{cmd.upper()} 订单已提交。\n状态: {status_msg}\n说明: {desc}\n订单ID: {order_id}")

        elif cmd == "assets":
            user, session = self.db.get_or_create_user(user_id)
            holdings = session.query(UserHolding).filter_by(user_id=user_id).all()
            
            msg = f"【用户资产 - {user_name}】\n"
            msg += f"可用资金: {user.balance:.2f}\n"
            msg += "持仓:\n"
            
            holdings_dict = {}
            has_holdings = False
            for h in holdings:
                if h.amount > 0.0001:
                    current_price = self.market.prices.get(h.symbol, 0)
                    value = h.amount * current_price
                    holdings_dict[h.symbol] = value
                    msg += f"- {h.symbol}: {h.amount:.4f} (市值: {value:.2f})\n"
                    has_holdings = True
            
            if not has_holdings:
                msg += "无\n"
                
            session.close()
            
            # Plot
            img_buf = plotter.plot_holdings_multi(user.balance, holdings_dict)
            img_path = self._save_temp_image(img_buf)
            if img_path:
                yield event.image_result(img_path)
            
            yield event.plain_result(msg)

        elif cmd == "orders":
            session = self.db.get_session()
            orders = session.query(Order).filter_by(user_id=user_id, status=OrderStatus.PENDING).all()
            session.close()
            
            if not orders:
                yield event.plain_result("当前无挂单。")
            else:
                msg = "【当前挂单】\n"
                for o in orders:
                    msg += f"ID:{o.id} {o.order_type.value} {o.symbol} {o.amount} @ {o.price}\n"
                yield event.plain_result(msg)

        elif cmd == "cancel":
            if len(args) < 3:
                yield event.plain_result("请输入订单ID")
                return
            try:
                oid = int(args[2])
                session = self.db.get_session()
                order = session.query(Order).filter_by(id=oid, user_id=user_id, status=OrderStatus.PENDING).first()
                if order:
                    order.status = OrderStatus.CANCELLED
                    session.commit()
                    msg = "订单已撤销。"
                else:
                    msg = "订单不存在或无法撤销。"
                session.close()
                yield event.plain_result(msg)
            except ValueError:
                yield event.plain_result("订单ID必须是数字")

        elif cmd == "reset":
            if not is_admin():
                 yield event.plain_result("权限不足")
                 return
            # Admin only for now, or user self-reset? Let's allow user self-reset for fun
            user, session = self.db.get_or_create_user(user_id)
            user.balance = 10000.0
            # Reset holdings
            session.query(UserHolding).filter_by(user_id=user_id).delete()
            session.query(Order).filter_by(user_id=user_id).delete()
            session.commit()
            session.close()
            yield event.plain_result("账户已重置。")

        elif cmd == "admin":
            if not is_admin():
                yield event.plain_result("权限不足")
                return
            
            if len(args) < 3:
                yield event.plain_result("Usage: /zrb admin [open|close]")
                return
                
            sub = args[2]
            if sub == "open":
                self.market.set_open(True)
                yield event.plain_result("市场已开启。")
            elif sub == "close":
                self.market.set_open(False)
                yield event.plain_result("市场已休市。")
            else:
                yield event.plain_result("未知指令")
