# astrbot-plugin-zirunbi (孜然币模拟炒股)

AstrBot 的一款多币种虚拟加密货币交易模拟插件。在群聊中体验模拟炒股的乐趣，体验“韭菜”的起起落落！

## ✨ 功能特性

*   **📈 多币种实时市场**：支持 **ZRB (孜然币)**、**STAR (星星币)**、**SHEEP (小羊币)**、**XIANGZI (祥子币)**、**MIAO (喵喵币)**、**QUNZHU (群主币)**、**IDEAL (理想币)**、**FEN (芬币)** 八种虚拟货币。
*   **🇨🇳 中国时区支持**：所有交易时间与 K 线图均采用 **UTC+8** 时间，符合国内用户习惯。
*   **🌐 Web 端交易平台**：提供独立的 Web 界面，支持账号登录、实时行情查看和快速交易，操作更便捷。
*   **⚡ 智能交易系统**：
    *   **3分钟** 周期价格更新机制。
    *   **即时撮合**：市价单立即成交，限价单即时判定。
    *   包含交易手续费机制 (0.1%)。
*   **� 专业可视化**：
    *   集成 `mplfinance` 生成专业 K 线图。
    *   自动生成账户持仓分布饼图。
*   **� 市场情报系统**：随机生成市场新闻快讯，增加沉浸感。
*   **📅 交易日报**：一键生成今日盈亏与交易统计报告。
*   **🛠️ 管理员调控**：支持管理员手动 **开市/休市**，掌控市场节奏。

## 📦 安装

1.  **下载插件**  
    将 `astrbot-plugin-zirunbi` 文件夹放置在 AstrBot 的 `data/plugins/` 目录下。

2.  **安装依赖**  
    插件依赖数据分析和绘图库，请在 AstrBot 运行环境中执行：
    ```bash
    pip install mplfinance pandas matplotlib sqlalchemy
    ```

3.  **重启 AstrBot**  
    重启后即可加载插件。

### Web 端使用

1.  **注册 Web 账号**：
    在 Bot 聊天窗口（建议私聊）发送：
    ```
    /zrb register <密码>
    ```
    Bot 将回复您的登录账号（QQ号）和 Web 访问地址。

2.  **访问 Web 界面**：
    在浏览器中打开 Bot 回复的地址，使用 QQ 号和刚才设置的密码登录。

3.  **开始交易**：
    Web 端提供直观的行情列表和交易面板，操作与指令同步。

### 插件配置

在 AstrBot 管理面板中配置插件：

*   **initial_price**: 初始价格基准（默认 100.0）
*   **volatility**: 市场波动率 (0.01 - 0.5)
*   **update_interval**: 市场价格更新间隔（秒）
*   **admin_ids**: 管理员 QQ 号列表（用于开关市）
*   **font_path**: 中文字体文件路径（可选，修复乱码）
*   **web_port**: Web 服务端口（默认 8000）
*   **web_public_url**: Web 公开访问域名（可选，如 http://example.com:8000）

## 🎮 指令列表

插件主命令为 `/zrb`。

### 基础指令

| 指令格式 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/zrb` 或 `/zrb help` | 查看帮助菜单 | - |
| `/zrb price [币种]` | 查看当前实时价格 | `/zrb price` (所有)<br>`/zrb price STAR` |
| `/zrb kline <币种>` | 生成并查看指定币种的 K 线图 | `/zrb kline ZRB` |
| `/zrb assets` | 查看我的账户资产、持仓及可视化饼图 | - |
| `/zrb buy <币种> <数量> [价格]` | **买入**。不填价格则为市价单，填价格则为限价单 | `/zrb buy STAR 100`<br>`/zrb buy ZRB 50 95.0` |
| `/zrb sell <币种> <数量> [价格]` | **卖出**。规则同上 | `/zrb sell SHEEP 50` |
| `/zrb orders` | 查看当前未成交的挂单 | - |
| `/zrb cancel <ID>` | 撤销指定 ID 的挂单（ID 可通过 `/zrb orders` 查看） | `/zrb cancel 12` |
| `/zrb news` | 查看最新的市场新闻快讯 | - |
| `/zrb today` | 查看今日交易日报（今日成交统计及当前币价） | - |

### 管理员指令

> 需要在配置 `admin_ids` 中添加发送者的 User ID。

*   `/zrb admin open`: **开市**，开启市场交易。
*   `/zrb admin close`: **休市**，暂停市场交易和价格波动。
*   `/zrb reset`: 重置自己的账户（资产恢复初始值）。

## ⚠️ 免责声明

*   本插件仅供娱乐，所有“资金”、“行情”均为虚拟数据。
*   **不涉及任何真实货币交易**。
*   投资有风险，（虚拟）入市需谨慎。

## 📝 开发者

*   **Author**: LumineStory
*   **Repository**: [github.com/oyxning/astrbot-plugin-zirunbi](https://github.com/oyxning/astrbot-plugin-zirunbi)
*   **Version**: 1.1.0
