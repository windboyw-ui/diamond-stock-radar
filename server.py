"""
鑽石股雷達 — Flask 後端 v6
修正項目：
  1. 修正所有 HTTP 404 — 使用多來源備援機制
  2. 股票名稱顯示中文 — 內建中文名稱字典
  3. 多 API 來源整合：Yahoo Finance + 台灣證交所 Open API + FinMind + Fugle + Alpha Vantage
     優先順序：TWSE Open API → FinMind → Yahoo Finance → Fugle → Alpha Vantage
  4. 任一條件符合即列出
  5. 所有指標日K線計算
執行：python server.py → http://localhost:5000
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import ta
import time
import requests
import warnings
import os
warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder=".")
CORS(app)

# =====================================================
#  API 金鑰設定（免費可留空，系統自動降級）
#  FinMind: https://finmindtrade.com/ 免費註冊取得
#  Fugle:   https://developer.fugle.tw/ 免費申請
#  Alpha Vantage: https://www.alphavantage.co/support/#api-key 免費
# =====================================================
FINMIND_TOKEN   = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoid2luZGJveXciLCJlbWFpbCI6IndpbmRib3l3QGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.54xApaszWF4L2xreRzKu0ZMf2DJon3cSfbIAzWtTuaw"   # 填入 FinMind token（留空=不使用）
FUGLE_API_KEY   = ""   # 填入 Fugle API Key（留空=不使用）
ALPHA_VANTAGE_KEY = ""  # 填入 Alpha Vantage Key（留空=不使用）

# =====================================================
#  中文名稱字典（避免 Yahoo 回傳英文或 404）
# =====================================================
CHINESE_NAMES = {
    "2330": "台積電",    "2303": "聯電",      "2454": "聯發科",
    "2382": "廣達",      "2317": "鴻海",      "2308": "台達電",
    "2357": "華碩",      "2353": "宏碁",      "2379": "瑞昱",
    "2356": "英業達",    "2325": "矽品",      "2319": "智邦",
    "2327": "國巨",      "2344": "華邦電",    "2337": "旺宏",
    "2351": "順德",      "2367": "燿華",      "2376": "技嘉",
    "2383": "台光電",    "2388": "威盛",      "2408": "南亞科",
    "2412": "中華電",    "2439": "美律",      "2492": "華新科",
    "2049": "上銀",      "2313": "華通",      "1301": "台塑",
    "1537": "廣隆",      "1563": "皇田",      "1590": "亞德客",
    "1626": "艾姆勒",    "2358": "廷鑫",      "2368": "金像電",
    "3005": "神基",      "3006": "晶豪科",    "3008": "大立光",
    "3016": "嘉澤",      "3017": "奇鋐",      "3019": "亞泰",
    "3034": "聯詠",      "3035": "智原",      "3037": "欣興",
    "3044": "健鼎",      "3047": "訊舟",      "3062": "建漢",
    "3078": "僑威",      "3081": "聯亞",      "3163": "波若威",
    "3189": "景碩",      "3228": "金麗科",    "3230": "德律",
    "3231": "緯創",      "3260": "威剛",      "3264": "欣銓",
    "3265": "台灣精工",  "3306": "鼎天",      "3324": "雙鴻",
    "3380": "明泰",      "3443": "創意",      "3481": "群創",
    "3491": "昇達科",    "3515": "旭宏",      "3530": "晶相光",
    "3532": "禾邦電子",  "3548": "兆利",      "3552": "同致",
    "3558": "神準",      "3563": "牧德",      "3594": "碩天",
    "3596": "鑫創",      "3597": "攸泰",      "3599": "宏碩",
    "3653": "健策",      "3661": "世芯",      "3665": "貿聯",
    "3711": "日月光",    "4919": "新唐",      "4938": "和碩",
    "4952": "凌通",      "4958": "臻鼎",      "4966": "譜瑞",
    "4968": "立積",      "4977": "眾達",      "4979": "光環",
    "5243": "乙盛",      "5274": "信驊",      "5285": "界霖",
    "5289": "菱生",      "5347": "世界先進",  "5483": "中美晶",
    "5876": "上海商銀",  "5880": "合庫金",    "6104": "創惟",
    "6166": "凌華",      "6196": "帆宣",      "6230": "超眾",
    "6235": "華孚",      "6239": "力成",      "6245": "立端",
    "6261": "久元",      "6266": "泰碩",      "6269": "台郡",
    "6271": "同欣電",    "6273": "祥碩",      "6274": "台燿",
    "6277": "宏正",      "6286": "立錡",      "6414": "樺漢",
    "6415": "矽力",      "6416": "瑞鼎",      "6442": "光聖",
    "6452": "康舒",      "6488": "環球晶",    "6505": "台塑化",
    "6523": "達爾",      "6669": "緯穎",      "6770": "力積電",
    "6782": "視動",      "6789": "采鈺",      "6792": "先豐",
    "6806": "盛達",      "8028": "昇陽半導體","8046": "南電",
    "2881": "富邦金",    "2882": "國泰金",    "3260": "威剛",
    "6510": "精測",      "6781": "AES-KY",
}

# =====================================================
#  掃描清單（已確認 .TW 上市 / .TWO 上櫃）
# =====================================================
GROUPS = {
    # ── 晶圓代工 ──
    "晶圓代工": [
        "2330.TW",  # 台積電
        "2303.TW",  # 聯電
        "5347.TW",  # 世界先進
        "6770.TW",  # 力積電
        "4968.TWO", # 富鴻網（上櫃晶圓）
        "6488.TWO", # 環球晶
        "5483.TWO", # 中美晶
    ],
    # ── IC設計 ──
    "IC設計": [
        "2454.TW",  # 聯發科
        "2379.TW",  # 瑞昱
        "3443.TW",  # 創意
        "3661.TW",  # 世芯-KY
        "3035.TW",  # 智原
        "3680.TW",  # 家登
        "6770.TW",  # 力積電
        "3034.TW",  # 聯詠
        "3711.TW",  # 日月光投控
        "4966.TW",  # 譜瑞-KY
        "2388.TW",  # 威盛
        "6416.TW",  # 瑞鼎
        "5274.TWO", # 信驊
        "6104.TWO", # 創惟
        "3532.TWO", # 台灣快捷
        "6261.TWO", # 動力-KY
        "4968.TWO", # 十銓科技
        "6414.TWO", # 樺漢
        "6789.TWO", # 采鈺
    ],
    # ── AI晶片 ──
    "AI晶片": [
        "3661.TW",  # 世芯-KY
        "3443.TW",  # 創意
        "3035.TW",  # 智原
        "3680.TW",  # 家登
        "2454.TW",  # 聯發科
        "3034.TW",  # 聯詠
        "5274.TWO", # 信驊
        "6104.TWO", # 創惟
    ],
    # ── 伺服器 ──
    "伺服器": [
        "2382.TW",  # 廣達
        "6669.TW",  # 緯穎
        "3231.TW",  # 緯創
        "4938.TW",  # 和碩
        "2357.TW",  # 華碩
        "2356.TW",  # 英業達
        "2353.TW",  # 宏碁
        "2317.TW",  # 鴻海
        "2308.TW",  # 台達電
        "3005.TW",  # 神基
        "6273.TW",  # 訊連
        "3017.TW",  # 奇鋐
        "6414.TWO", # 樺漢
        "3380.TWO", # 明泰
        "5274.TWO", # 信驊
        "3594.TWO", # 台灣精銳
        "6277.TWO", # 宇瞻
        "3306.TWO", # 鼎翰
        "6806.TWO", # 明緯
        "3552.TWO", # 同致
        "6523.TWO", # 達運精密
        "3665.TWO", # 貿聯-KY
        "2421.TW",  # Inventec 英業達（同2356）
    ],
    # ── 散熱模組 ──
    "散熱模組": [
        "3324.TWO", # 雙鴻
        "3653.TW",  # 健策
        "3017.TW",  # 奇鋐
        "2421.TW",  # 建準
        "3019.TW",  # 亞泰
        "6230.TW",  # 超眾
        "1626.TW",  # 艾姆勒
        "3515.TW",  # 莊頭北
        "3558.TW",  # 神準
        "2358.TW",  # 廷鑫
        "3597.TWO", # 攸泰
        "6452.TWO", # 康舒
        "3599.TWO", # 德城
        "5243.TWO", # 乙盛-KY
        "2368.TW",  # 金像電
    ],
    # ── PCB ──
    "PCB": [
        "4958.TW",  # 臻鼎-KY
        "3037.TW",  # Unimicron 欣興
        "2313.TW",  # 華通
        "3044.TW",  # 健鼎
        "2383.TW",  # 台光電
        "6213.TW",  # 聯茂
        "8046.TW",  # 南亞電路板
        "2368.TW",  # 金像電
        "3189.TW",  # 景碩
        "6274.TW",  # 台燿
        "2367.TW",  # 燿華
        "4952.TW",  # 台表科
        "6792.TWO", # 建碁
        "6789.TWO", # 采鈺
        "5285.TWO", # 界霖
        "6196.TWO", # 帆宣
        "3264.TWO", # 欣銓
        "2376.TW",  # 技嘉
    ],
    # ── CCL/基板 ──
    "CCL/基板": [
        "2383.TW",  # 台光電
        "6213.TW",  # 聯茂
        "8046.TW",  # 南亞電路板
        "2368.TW",  # 金像電
        "4958.TW",  # 臻鼎-KY
    ],
    # ── 光通訊模組 ──
    "光通訊模組": [
        "3163.TWO", # 波若威
        "3450.TW",  # 聯鈞
        "3234.TW",  # 光環
        "3363.TW",  # 上詮
        "3228.TW",  # 金麗科
        "6782.TW",  # 視覺人工智慧
        "4977.TW",  # 眾達-KY
        "6166.TW",  # 凌華
        "3548.TW",  # 兆利
        "6442.TW",  # 光聖
        "3081.TWO", # 聯亞光電
        "4979.TWO", # 晶睿
        "3491.TWO", # 昇銳
        "6245.TWO", # 立端
        "3047.TWO", # 訊舟
        "6806.TWO", # 明緯
        "3265.TWO", # 台灣精測
        "6792.TWO", # 建碁
    ],
    # ── 高速連接器 ──
    "高速連接器": [
        "2492.TW",  # 華新科
        "3023.TW",  # 信邦
        "6290.TW",  # 良維
        "2439.TW",  # 美律
        "2308.TW",  # 台達電
        "3665.TWO", # 貿聯-KY
        "3552.TWO", # 同致
    ],
    # ── 電源供應器 ──
    "電源供應器": [
        "2308.TW",  # 台達電
        "6282.TW",  # 康舒
        "6412.TW",  # 光寶科
        "6412.TW",  # 群電
        "2308.TW",  # 台達電
        "3665.TWO", # 貿聯-KY
        "6452.TWO", # 康舒
        "6523.TWO", # 達運精密
    ],
    # ── 被動元件 ──
    "被動元件": [
        "2327.TW",  # 國巨 YAGEO
        "2351.TW",  # 華新科 WALSIN
        "2492.TW",  # 華新科
        "2439.TW",  # 美律
        "2344.TW",  # 華邦電
        "2049.TW",  # 上銀
        "2319.TW",  # 智邦
        "2478.TW",  # 大毅
        "6173.TW",  # 信昌電
        "2458.TWO", # 義隆
        "3078.TWO", # 僑威
        "6277.TWO", # 宇瞻
        "2478.TW",  # 大毅
    ],
    # ── 記憶體/儲存 ──
    "記憶體/儲存": [
        "2408.TW",  # 南亞科
        "2344.TW",  # 華邦電
        "4919.TW",  # 新唐
        "5347.TW",  # 世界先進
        "3260.TW",  # 威剛
        "4966.TW",  # 譜瑞-KY
        "8271.TWO", # 宇瞻
        "8299.TWO", # 群聯
        "5289.TWO", # 宜鼎
        "6139.TWO", # 亞德諾
        "3006.TWO", # 晶豪科
        "3062.TWO", # 建漢
        "4983.TWO", # 可成（儲存相關）
    ],
    # ── AI軟體/平台 ──
    "AI軟體/平台": [
        "3029.TW",  # 零壹
        "6214.TWO", # 精誠
        "6689.TWO", # iCloud Valley
        "6752.TWO", # 叡揚
        "2412.TW",  # 中華電信
    ],
    # ── 雲端服務 ──
    "雲端服務": [
        "2412.TW",  # 中華電信
        "3045.TW",  # 台灣大哥大
        "4904.TW",  # 遠傳
        "3682.TW",  # 亞太電信
        "2308.TW",  # 台達電
    ],
    # ── 資料中心(IDC) ──
    "資料中心IDC": [
        "1527.TW",  # 鑽全
        "7765.TW",  # 中華系統整合
        "5314.TW",  # 新世紀資通
        "3234.TW",  # 光環新網
        "2421.TW",  # 建準
    ],
    # ── 機殼/機構件 ──
    "機殼機構件": [
        "8210.TW",  # 勤誠
        "3013.TW",  # 盈錸
        "2474.TW",  # 可成
        "2354.TW",  # 鴻準
        "3338.TWO", # 泰碩
        "6104.TWO", # 創惟
    ],
    # ── 傳輸晶片 ──
    "傳輸晶片": [
        "5269.TW",  # 祥碩
        "2379.TW",  # 瑞昱
        "4966.TW",  # 譜瑞-KY
        "6104.TWO", # 創惟
        "5274.TWO", # 信驊
    ],
    # ── 測試介面 ──
    "測試介面": [
        "6223.TW",  # 旺矽
        "3014.TW",  # 寶雅
        "6515.TWO", # 穎崴
        "6510.TWO", # 精測
        "6139.TWO", # 愛德萬
        "3264.TWO", # 欣銓
        "3265.TWO", # 台灣精測
    ],
    # ── 液冷/散熱液 ──
    "液冷散熱液": [
        "1338.TW",  # 奇鋐（水冷）
        "3324.TWO", # 雙鴻（液冷）
        "2421.TW",  # 建準
        "6669.TW",  # 緯穎（液冷伺服器）
        "3017.TW",  # 奇鋐
        "2376.TW",  # 技嘉
        "6452.TWO", # 泰碩
        "8210.TW",  # 勤誠
    ],
    # ── AI應用整合 ──
    "AI應用整合": [
        "3231.TW",  # 緯創
        "2382.TW",  # 廣達
        "6669.TW",  # 緯穎
        "2376.TW",  # 技嘉
        "6214.TWO", # 精誠
        "5274.TWO", # 信驊
    ],
    # ── 半導體龍頭 ──
    "半導體龍頭": [
        "2330.TW",  # 台積電
        "2454.TW",  # 聯發科
        "2303.TW",  # 聯電
        "6488.TWO", # 環球晶
        "5274.TWO", # 信驊
        "6789.TWO", # 采鈺
        "4968.TWO", # 十銓
    ],
    # ── CoWoS先進封裝 ──
    "CoWoS先進封裝": [
        "2330.TW",  # 台積電
        "3711.TW",  # 日月光投控
        "2325.TW",  # 矽品
        "3443.TW",  # 創意
        "3037.TW",  # 欣興
        "8046.TW",  # 南亞電路板
        "4958.TW",  # 臻鼎-KY
        "6239.TWO", # 浩鑫
        "6271.TWO", # 同欣電
        "6792.TWO", # 建碁
        "5289.TWO", # 宜鼎
        "3264.TWO", # 欣銓
        "3680.TW",  # 家登
    ],
    # ── AI機器人 ──
    "AI機器人": [
        "2382.TW",  # 廣達
        "2308.TW",  # 台達電
        "2049.TW",  # 上銀
        "1590.TW",  # 亞德客-KY
        "1563.TW",  # 中鋼構
        "3563.TWO", # 牧德
        "6414.TWO", # 樺漢
        "3230.TWO", # 德律
        "6196.TWO", # 帆宣
        "3552.TWO", # 同致
        "6266.TWO", # 富采
    ],
    # ── 光通訊（保留舊名） ──
    "光通訊": [
        "3228.TW",  # 金麗科
        "6782.TW",  # 視覺AI
        "4977.TW",  # 眾達-KY
        "6166.TW",  # 凌華
        "3548.TW",  # 兆利
        "6442.TW",  # 光聖
        "3163.TWO", # 波若威
        "3081.TWO", # 聯亞光電
        "4979.TWO", # 晶睿
        "3491.TWO", # 昇銳
        "6245.TWO", # 立端
        "3047.TWO", # 訊舟
        "6806.TWO", # 明緯
        "3265.TWO", # 台灣精測
        "6792.TWO", # 建碁
        "3450.TW",  # 聯鈞
        "3234.TW",  # 光環
        "3363.TW",  # 上詮
    ],
    # ── 網通設備 ──
    "網通設備": [
        "2319.TW",  # 智邦
        "2357.TW",  # 華碩
        "2353.TW",  # 宏碁
        "3380.TWO", # 明泰
        "6277.TWO", # 宇瞻
        "3306.TWO", # 鼎翰
        "4979.TWO", # 晶睿
        "3062.TWO", # 建漢
        "6806.TWO", # 明緯
        "3665.TWO", # 貿聯-KY
    ],
    # ── NVIDIA概念 ──
    "NVIDIA概念": [
        "2330.TW",  # 台積電
        "3034.TW",  # 聯詠
        "2382.TW",  # 廣達
        "6669.TW",  # 緯穎
        "3711.TW",  # 日月光
        "3443.TW",  # 創意
        "4958.TW",  # 臻鼎-KY
        "3037.TW",  # 欣興
        "5274.TWO", # 信驊
        "6792.TWO", # 建碁
    ],
    # ── Google概念 ──
    "Google概念": [
        "2330.TW",  # 台積電
        "3034.TW",  # 聯詠
        "2382.TW",  # 廣達
        "2357.TW",  # 華碩
        "6669.TW",  # 緯穎
        "3231.TW",  # 緯創
        "4938.TW",  # 和碩
        "3189.TW",  # 景碩
        "6415.TW",  # 昆盈
        "5274.TWO", # 信驊
        "6414.TWO", # 樺漢
        "3306.TWO", # 鼎翰
        "3552.TWO", # 同致
    ],
    # ── AMD概念 ──
    "AMD概念": [
        "2330.TW",  # 台積電
        "3034.TW",  # 聯詠
        "2382.TW",  # 廣達
        "6669.TW",  # 緯穎
        "3231.TW",  # 緯創
        "3016.TW",  # 嘉澤
        "2383.TW",  # 台光電
        "3189.TW",  # 景碩
        "6274.TW",  # 台燿
        "5274.TWO", # 信驊
        "6104.TWO", # 創惟
        "6792.TWO", # 建碁
        "3596.TWO", # 江興鍛
    ],
    # ── 金融 ──
    "金融": [
        "2881.TW",  # 富邦金
        "2882.TW",  # 國泰金
        "2412.TW",  # 中華電
        "1301.TW",  # 台塑
        "6505.TW",  # 台塑化
        "5876.TWO", # 上海商銀
        "5880.TWO", # 合庫金
    ],
}


def is_valid_symbol(s):
    code = s.replace(".TWO","").replace(".TW","")
    return code.isdigit()

_all = []
for g, lst in GROUPS.items():
    _all.extend(lst)
WATCHLIST = list(dict.fromkeys(s for s in _all if is_valid_symbol(s)))

CODE_TO_GROUP = {}
for g, lst in GROUPS.items():
    for s in lst:
        code = s.replace(".TWO","").replace(".TW","")
        if code not in CODE_TO_GROUP:
            CODE_TO_GROUP[code] = []
        CODE_TO_GROUP[code].append(g)

print(f"  📋 掃描清單共 {len(WATCHLIST)} 檔（上市+上櫃，去重）")

# 快取：避免同一執行期重複查詢
_data_cache = {}   # { symbol → data_dict }

# =====================================================
#  工具函式
# =====================================================
def get_code(symbol):
    return symbol.replace(".TWO","").replace(".TW","")

def get_chinese_name(code, fallback=""):
    return CHINESE_NAMES.get(code, fallback)

def safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (pd.isna(f) or f != f) else f
    except:
        return default

def calc_indicators(df):
    """
    從日K DataFrame 計算所有技術指標：
      - KD、MACD（原有）
      - 底部型態（W底、圓底、均線糾結翻揚）
      - 主力/外資成本價估算（均量加權）
      - 帶量長紅K突破20日線
    """
    if df is None or len(df) < 30:
        return None
    df = df.copy()
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    # ── KD ──
    stoch      = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=9, smooth_window=3)
    df["K"]    = stoch.stoch()
    df["D"]    = stoch.stoch_signal()

    # ── MACD ──
    macd_obj       = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["DIF"]      = macd_obj.macd()
    df["DEA"]      = macd_obj.macd_signal()
    df["MACD_bar"] = macd_obj.macd_diff()

    # ── 移動平均線 ──
    df["MA5"]  = close.rolling(5).mean()
    df["MA10"] = close.rolling(10).mean()
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean() if len(df) >= 60 else close.rolling(len(df)).mean()

    # ── 成交量移動平均 ──
    df["VOL_MA5"]  = volume.rolling(5).mean()
    df["VOL_MA20"] = volume.rolling(20).mean()

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    k    = safe_float(latest["K"],   50.0)
    d    = safe_float(latest["D"],   50.0)
    dif  = safe_float(latest["DIF"],  0.0)
    dea  = safe_float(latest["DEA"],  0.0)
    pdif = safe_float(prev["DIF"],    0.0)
    pdea = safe_float(prev["DEA"],    0.0)

    price_now  = safe_float(latest["Close"], 0.0)
    price_prev = safe_float(prev["Close"],   0.0)
    ma5   = safe_float(latest["MA5"],  0.0)
    ma10  = safe_float(latest["MA10"], 0.0)
    ma20  = safe_float(latest["MA20"], 0.0)
    ma60  = safe_float(latest["MA60"], 0.0)
    vol_now    = safe_float(latest["Volume"],   0.0)
    vol_ma5    = safe_float(latest["VOL_MA5"],  0.0)
    vol_ma20   = safe_float(latest["VOL_MA20"], 0.0)

    macd_cross = (dif > dea) and (pdif <= pdea)
    macd_near  = (dif < dea) and \
                 (abs(dif-dea) < abs(pdif-pdea)) and \
                 (abs(dif-dea) < 0.5)

    # ══════════════════════════════════════════
    #  新條件 1：底部型態判斷
    #  使用最近 60 根日K，偵測三種底部形態
    # ══════════════════════════════════════════
    bottom_type   = ""       # 底部型態名稱
    bottom_signal = False    # 是否有底部訊號

    recent = df.tail(60).copy()
    rc     = recent["Close"].values
    rh     = recent["High"].values
    rl     = recent["Low"].values
    rv     = recent["Volume"].values
    n      = len(rc)

    if n >= 40:
        # 找區間最低點
        min_idx = int(pd.Series(rl).idxmin())
        min_low = rl[min_idx]

        # ── W底偵測 ──
        # 條件：兩個低點高度接近（差距<5%），中間有反彈（>低點的3%），
        #       右低比左低略高（right_low > left_low），現價突破頸線
        try:
            left_section  = rc[:n//2]
            right_section = rc[n//2:]
            left_low_idx  = int(pd.Series(rl[:n//2]).idxmin())
            right_low_idx = int(pd.Series(rl[n//2:]).idxmin()) + n//2

            left_low  = rl[left_low_idx]
            right_low = rl[right_low_idx]
            neckline  = max(rc[left_low_idx:right_low_idx]) if right_low_idx > left_low_idx else 0

            low_diff_pct = abs(left_low - right_low) / (left_low + 1e-9)
            rebound      = (neckline - min(left_low, right_low)) / (min(left_low, right_low) + 1e-9)

            if (low_diff_pct < 0.05 and
                rebound > 0.03 and
                right_low >= left_low * 0.98 and
                price_now > neckline * 0.99):
                bottom_type   = "W底"
                bottom_signal = True
        except:
            pass

        # ── 圓底偵測（弧形底）──
        # 條件：最低點在中段，兩端比中間高，呈對稱弓形，現價站上MA20
        if not bottom_signal:
            try:
                third = n // 3
                left_avg  = float(pd.Series(rc[:third]).mean())
                mid_min   = float(pd.Series(rc[third:2*third]).min())
                right_avg = float(pd.Series(rc[2*third:]).mean())

                if (mid_min < left_avg * 0.97 and
                    mid_min < right_avg * 0.97 and
                    abs(left_avg - right_avg) / (left_avg + 1e-9) < 0.08 and
                    price_now > ma20 * 0.99):
                    bottom_type   = "圓底"
                    bottom_signal = True
            except:
                pass

        # ── 均線糾結翻揚（多頭排列形成）──
        # 條件：MA5/MA10/MA20 三線從糾結狀態開始發散，MA5 > MA10 > MA20
        if not bottom_signal:
            try:
                prev5  = safe_float(df.iloc[-6]["MA5"],  0)
                prev10 = safe_float(df.iloc[-6]["MA10"], 0)
                prev20 = safe_float(df.iloc[-6]["MA20"], 0)

                was_tangled = abs(prev5 - prev20) / (prev20 + 1e-9) < 0.03
                now_sorted  = (ma5 > ma10 > ma20 > 0)
                rising      = (ma5 > prev5 and ma10 > prev10)

                if was_tangled and now_sorted and rising:
                    bottom_type   = "均線糾結翻揚"
                    bottom_signal = True
            except:
                pass

        # ── 箱型整理突破 ──
        # 條件：過去30天低點高點壓縮在8%範圍，今日突破上緣
        if not bottom_signal:
            try:
                box_period = rc[max(0,n-30):n-1]
                box_high   = float(pd.Series(box_period).max())
                box_low    = float(pd.Series(box_period).min())
                box_range  = (box_high - box_low) / (box_low + 1e-9)
                if box_range < 0.08 and price_now > box_high * 1.005:
                    bottom_type   = "箱型突破"
                    bottom_signal = True
            except:
                pass

    # ══════════════════════════════════════════
    #  新條件 2：主力成本價 & 外資成本價估算
    #  主力成本：近60日 成交量加權平均價（VWAP60）
    #  外資成本：近120日 VWAP（模擬外資持倉周期較長）
    #  ※ 真實外資/主力成本需籌碼API，此為合理統計估算
    # ══════════════════════════════════════════
    def vwap(df_slice):
        c = df_slice["Close"].values
        v = df_slice["Volume"].values
        total_vol = v.sum()
        if total_vol == 0:
            return 0.0
        return float((c * v).sum() / total_vol)

    inst_cost    = 0.0   # 主力成本（VWAP 60日）
    foreign_cost = 0.0   # 外資成本（VWAP 120日）
    margin_cost  = 0.0   # 融資成本（VWAP 20日，短線融資持倉周期較短）

    try:
        slice60  = df.tail(60)
        inst_cost = round(vwap(slice60), 2)
    except:
        pass

    try:
        slice120 = df.tail(120) if len(df) >= 120 else df.tail(len(df))
        foreign_cost = round(vwap(slice120), 2)
    except:
        pass

    try:
        slice20 = df.tail(20)
        margin_cost = round(vwap(slice20), 2)
    except:
        pass

    # 判斷現價是否低於成本價
    below_inst_cost    = (inst_cost > 0 and price_now < inst_cost)
    below_foreign_cost = (foreign_cost > 0 and price_now < foreign_cost)
    below_margin_cost  = (margin_cost > 0 and price_now < margin_cost)

    inst_cost_gap    = round((inst_cost - price_now) / inst_cost * 100, 1)       if inst_cost > 0    else 0
    foreign_cost_gap = round((foreign_cost - price_now) / foreign_cost * 100, 1) if foreign_cost > 0 else 0
    margin_cost_gap  = round((margin_cost - price_now) / margin_cost * 100, 1)   if margin_cost > 0  else 0

    # ══════════════════════════════════════════
    #  新條件 3：帶量長紅K突破20日均線
    #  條件：
    #    a. 今日為紅K（收 > 開）
    #    b. 漲幅 >= 2%（長紅K門檻）
    #    c. 收盤站上 MA20
    #    d. 成交量 >= 近5日均量的 1.5 倍（帶量）
    #    e. 昨日收盤 < MA20（真正突破，非已在線上）
    # ══════════════════════════════════════════
    open_now   = safe_float(latest["Open"], 0.0)
    prev_close = safe_float(prev["Close"],  0.0)
    prev_ma20  = safe_float(prev["MA20"],   0.0)

    is_red_k        = price_now > open_now
    body_pct        = (price_now - open_now) / (open_now + 1e-9) * 100
    is_long_red     = is_red_k and body_pct >= 2.0
    above_ma20      = price_now > ma20 > 0
    prev_below_ma20 = prev_close < prev_ma20 if prev_ma20 > 0 else False
    is_heavy_vol    = vol_now >= vol_ma5 * 1.5 if vol_ma5 > 0 else False

    # 突破確認（今日突破 + 帶量 + 長紅）
    vol_break_ma20 = (is_long_red and above_ma20 and prev_below_ma20 and is_heavy_vol)

    # 僅帶量站上20日線（條件較寬鬆）
    vol_above_ma20 = (is_red_k and above_ma20 and is_heavy_vol and not prev_below_ma20)

    # 成交量倍數
    vol_ratio = round(vol_now / vol_ma5, 2) if vol_ma5 > 0 else 0.0

    # ── 三線聚集（日K：MA5 / MA20 / MA60）──
    # 三條均線最大值與最小值之差 / 收盤價 < 閾值
    # 閾值 3%：三線靠攏但尚未爆發，是進場前的醞釀訊號
    ma_conv_pct = 0.0
    ma_converge_day = False
    if ma5 > 0 and ma20 > 0 and ma60 > 0 and price_now > 0:
        ma_max = max(ma5, ma20, ma60)
        ma_min = min(ma5, ma20, ma60)
        ma_conv_pct = round((ma_max - ma_min) / price_now * 100, 2)
        ma_converge_day = (ma_conv_pct < 3.0)

    return dict(
        price=round(price_now, 1),
        volume=int(safe_float(latest.get("Volume", 0), 0)),
        vol_ratio=vol_ratio,
        K=round(k,1), D=round(d,1),
        DIF=round(dif,4), DEA=round(dea,4),
        MACD_bar=round(safe_float(latest.get("MACD_bar",0)),4),
        macd_cross=macd_cross, macd_near=macd_near,
        ma5=round(ma5,2), ma10=round(ma10,2),
        ma20=round(ma20,2), ma60=round(ma60,2),
        # 底部型態
        bottom_signal=bottom_signal,
        bottom_type=bottom_type,
        # 主力/外資/融資成本
        inst_cost=inst_cost,
        foreign_cost=foreign_cost,
        margin_cost=margin_cost,
        below_inst_cost=below_inst_cost,
        below_foreign_cost=below_foreign_cost,
        below_margin_cost=below_margin_cost,
        inst_cost_gap=inst_cost_gap,
        foreign_cost_gap=foreign_cost_gap,
        margin_cost_gap=margin_cost_gap,
        # 帶量突破20日線
        vol_break_ma20=vol_break_ma20,
        vol_above_ma20=vol_above_ma20,
        body_pct=round(body_pct,2),
        above_ma20=above_ma20,
        is_heavy_vol=is_heavy_vol,
        # 三線聚集（日K MA5/20/60）
        ma_converge_day=ma_converge_day,
        ma_conv_pct=ma_conv_pct,
    )

# =====================================================
#  60分鐘K線 666戰法判斷（三條件）
# =====================================================
def calc_666_signal(symbol):
    """
    下載 60 分鐘K線，計算以下三個條件：
      條件①：60分K 收盤價站上 60MA
      條件②：KD(60,3,3) 黃金交叉（K 上穿 D）且 K值在 50~60 區間
      條件③：5MA 上穿 60MA 黃金交叉（容許近 3 根確認）
    signal_666 = 三個條件同時成立
    """
    empty = dict(
        signal_666=False,
        # 均線
        ma5_60min=0.0, ma20_60min=0.0, ma60_60min=0.0,
        price_60min=0.0,
        # 條件①
        above_60ma=False,
        # 條件②
        kd60_K=0.0, kd60_D=0.0,
        kd60_golden=False, kd60_k_above50=False,
        # 條件③
        ma5_cross_ma60=False, ma5_above_ma60=False,
    )
    try:
        tk   = yf.Ticker(symbol)
        df60 = tk.history(period="60d", interval="60m")
        if df60 is None or df60.empty or len(df60) < 65:
            return empty

        df60.index = pd.to_datetime(df60.index).tz_localize(None)
        close = df60["Close"].astype(float)
        high  = df60["High"].astype(float)
        low   = df60["Low"].astype(float)

        if len(close) < 60:
            return empty

        # ── 均線 ──
        ma5_s  = close.rolling(5).mean()
        ma20_s = close.rolling(20).mean()
        ma60_s = close.rolling(60).mean()

        ma5       = float(ma5_s.iloc[-1])
        ma20      = float(ma20_s.iloc[-1])
        ma60      = float(ma60_s.iloc[-1])
        price_now = float(close.iloc[-1])

        if ma60 == 0:
            return empty

        # ── 條件①：收盤站上 60MA ──
        above_60ma = (price_now > ma60)

        # ── 條件②：KD(60,3,3) 黃金交叉且 K > 50 ──
        lowest  = low.rolling(60).min()
        highest = high.rolling(60).max()
        rsv = ((close - lowest) / (highest - lowest + 1e-9) * 100).fillna(50)

        K_val, D_val = 50.0, 50.0
        K_arr, D_arr = [], []
        for rv in rsv:
            K_val = K_val * 2/3 + float(rv) * 1/3
            D_val = D_val * 2/3 + K_val * 1/3
            K_arr.append(K_val)
            D_arr.append(D_val)

        K_now  = round(K_arr[-1], 1)
        D_now  = round(D_arr[-1], 1)
        K_prev = K_arr[-2]
        D_prev = D_arr[-2]

        # 黃金交叉：前一根 K<=D，本根 K>D，容許近 3 根確認
        kd60_golden = (K_prev <= D_prev) and (K_now > D_now)
        if not kd60_golden:
            for lag in range(1, 4):
                if len(K_arr) > lag + 1:
                    if (K_arr[-2-lag] <= D_arr[-2-lag]) and (K_arr[-1-lag] > D_arr[-1-lag]) and (K_now > D_now):
                        kd60_golden = True
                        break

        kd60_k_above50 = (50 < K_now <= 60)   # K 值在 50~60 區間

        # ── 條件③：5MA 上穿 60MA 黃金交叉 ──
        ma5_prev  = float(ma5_s.iloc[-2])
        ma60_prev = float(ma60_s.iloc[-2])
        ma5_cross_now = (ma5_prev <= ma60_prev) and (ma5 > ma60)

        ma5_cross_ma60 = ma5_cross_now
        if not ma5_cross_ma60:
            for lag in range(1, 4):
                if len(ma5_s) > lag + 1:
                    m5_a  = float(ma5_s.iloc[-1-lag])
                    m60_a = float(ma60_s.iloc[-1-lag])
                    m5_b  = float(ma5_s.iloc[-2-lag])
                    m60_b = float(ma60_s.iloc[-2-lag])
                    if (m5_b <= m60_b) and (m5_a > m60_a) and (ma5 > ma60):
                        ma5_cross_ma60 = True
                        break

        ma5_above_ma60 = (ma5 > ma60)

        # ── 三個條件全部成立 ──
        signal_666 = above_60ma and kd60_golden and kd60_k_above50 and ma5_cross_ma60

        return dict(
            signal_666      = signal_666,
            ma5_60min       = round(ma5,  2),
            ma20_60min      = round(ma20, 2),
            ma60_60min      = round(ma60, 2),
            price_60min     = round(price_now, 2),
            above_60ma      = above_60ma,
            kd60_K          = K_now,
            kd60_D          = D_now,
            kd60_golden     = kd60_golden,
            kd60_k_above50  = kd60_k_above50,
            ma5_cross_ma60  = ma5_cross_ma60,
            ma5_above_ma60  = ma5_above_ma60,
        )
    except Exception as e:
        return empty
# =====================================================
#  來源 1：台灣證交所 Open API（免費，無需金鑰）
# =====================================================
def fetch_twse_price(code):
    """從 TWSE Open API 取得即時報價（上市股）"""
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{code}.tw&json=1&delay=0"
        r = requests.get(url, timeout=6)
        if r.status_code != 200:
            return None
        j = r.json()
        items = j.get("msgArray", [])
        if not items:
            return None
        d = items[0]
        price = float(d.get("z","0") or d.get("y","0") or 0)
        name  = d.get("n","") or d.get("nf","")
        return {"price": price, "name": name} if price else None
    except:
        return None

def fetch_tpex_price(code):
    """從 TPEx API 取得即時報價（上櫃股）"""
    try:
        url = f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes?stockCode={code}"
        r = requests.get(url, timeout=6)
        if r.status_code != 200:
            return None
        items = r.json()
        for item in items:
            if str(item.get("SecuritiesCompanyCode","")) == str(code):
                price = float(item.get("Close","0") or 0)
                name  = item.get("CompanyAbbreviation","")
                return {"price": price, "name": name} if price else None
        return None
    except:
        return None

def fetch_twse_history(code, is_otc=False):
    """從 TWSE/TPEx API 取得近 6 個月日K歷史資料"""
    frames = []
    today  = pd.Timestamp.now()
    for months_back in range(6, -1, -1):
        dt = today - pd.DateOffset(months=months_back)
        ym = dt.strftime("%Y%m")
        try:
            if is_otc:
                url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={ym}&stkno={code}&s=0,asc&o=json"
                r   = requests.get(url, timeout=8)
                j   = r.json()
                rows= j.get("aaData",[])
                records=[]
                for row in rows:
                    try:
                        date_str = row[0].replace("/","-")
                        date     = pd.to_datetime("20"+date_str if len(date_str)==8 else date_str)
                        records.append({
                            "Date":   date,
                            "Open":   float(row[4].replace(",","")),
                            "High":   float(row[5].replace(",","")),
                            "Low":    float(row[6].replace(",","")),
                            "Close":  float(row[7].replace(",","")),
                            "Volume": float(row[1].replace(",","")),
                        })
                    except:
                        continue
                if records:
                    frames.append(pd.DataFrame(records).set_index("Date"))
            else:
                url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={ym}01&stockNo={code}&response=json"
                r   = requests.get(url, timeout=8)
                j   = r.json()
                rows= j.get("data",[])
                records=[]
                for row in rows:
                    try:
                        parts = row[0].split("/")
                        year  = int(parts[0]) + 1911
                        date  = pd.to_datetime(f"{year}/{parts[1]}/{parts[2]}")
                        records.append({
                            "Date":   date,
                            "Open":   float(row[3].replace(",","")),
                            "High":   float(row[4].replace(",","")),
                            "Low":    float(row[5].replace(",","")),
                            "Close":  float(row[6].replace(",","")),
                            "Volume": float(row[1].replace(",","")),
                        })
                    except:
                        continue
                if records:
                    frames.append(pd.DataFrame(records).set_index("Date"))
        except:
            continue
    if not frames:
        return None
    df = pd.concat(frames).sort_index().drop_duplicates()
    return df if len(df) >= 30 else None

# =====================================================
#  來源 2：FinMind API（免費，需 token）
# =====================================================
def fetch_finmind_history(code):
    if not FINMIND_TOKEN:
        return None
    try:
        end   = pd.Timestamp.now().strftime("%Y-%m-%d")
        start = (pd.Timestamp.now() - pd.DateOffset(months=7)).strftime("%Y-%m-%d")
        url   = "https://api.finmindtrade.com/api/v4/data"
        params = dict(
            dataset="TaiwanStockPrice",
            data_id=code,
            start_date=start,
            end_date=end,
            token=FINMIND_TOKEN,
        )
        r = requests.get(url, params=params, timeout=10)
        j = r.json()
        rows = j.get("data",[])
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"open":"Open","max":"High","min":"Low","close":"Close","Trading_Volume":"Volume"})
        df = df[["Date","Open","High","Low","Close","Volume"]].set_index("Date").sort_index()
        return df if len(df) >= 30 else None
    except:
        return None

def fetch_finmind_fundamentals(code):
    if not FINMIND_TOKEN:
        return {}
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        result = {}
        # ROE
        r = requests.get(url, params=dict(dataset="TaiwanStockFinancialStatements", data_id=code, token=FINMIND_TOKEN), timeout=8)
        j = r.json()
        rows = j.get("data",[])
        if rows:
            for row in reversed(rows):
                if row.get("type") == "ROE":
                    result["roe"] = float(row.get("value",0))
                    break
        return result
    except:
        return {}

# =====================================================
#  來源 3：Yahoo Finance（主力，但有 404 問題）
# =====================================================
def fetch_yahoo(symbol):
    try:
        tk   = yf.Ticker(symbol)
        hist = tk.history(period="6mo", interval="1d")
        if hist is None or hist.empty or len(hist) < 30:
            return None, None
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        info = tk.info or {}
        return hist, info
    except:
        return None, None

# =====================================================
#  來源 4：Fugle API（需金鑰，備援）
# =====================================================
def fetch_fugle_price(code):
    if not FUGLE_API_KEY:
        return None
    try:
        url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{code}"
        r   = requests.get(url, headers={"X-API-KEY": FUGLE_API_KEY}, timeout=6)
        if r.status_code != 200:
            return None
        j = r.json()
        return {"price": float(j.get("lastPrice",0) or 0), "name": j.get("name","")}
    except:
        return None

# =====================================================
#  來源 5：Alpha Vantage（需金鑰，主要用於基本面）
# =====================================================
def fetch_alpha_fundamentals(code):
    if not ALPHA_VANTAGE_KEY:
        return {}
    try:
        # Alpha Vantage 台股格式：代號.TW（僅支援部分台股）
        symbol = f"{code}.TW"
        url    = "https://www.alphavantage.co/query"
        r = requests.get(url, params=dict(
            function="OVERVIEW", symbol=symbol, apikey=ALPHA_VANTAGE_KEY
        ), timeout=8)
        j = r.json()
        if "Symbol" not in j:
            return {}
        result = {}
        if j.get("ReturnOnEquityTTM"):
            result["roe"] = float(j["ReturnOnEquityTTM"]) * 100
        if j.get("TrailingPE"):
            result["pe"] = float(j["TrailingPE"])
        if j.get("DebtToEquityRatio"):
            result["debt_ratio"] = float(j["DebtToEquityRatio"])
        if j.get("EPS"):
            result["eps"] = float(j["EPS"])
        return result
    except:
        return {}

# =====================================================
#  核心整合函式：多來源合併取得股票資料
# =====================================================
def get_stock_data(symbol):
    if symbol in _data_cache:
        return _data_cache[symbol]

    code   = get_code(symbol)
    is_otc = ".TWO" in symbol
    market = "上櫃" if is_otc else "上市"

    print(f"  [{symbol}]", end=" ")

    # ── Step 1：取得中文名稱（從字典優先）──
    cn_name = get_chinese_name(code, "")

    # ── Step 2：日K歷史資料（多來源嘗試）──
    hist   = None
    source = ""

    # 先試 Yahoo Finance（最快）
    hist_yf, info_yf = fetch_yahoo(symbol)
    if hist_yf is not None and len(hist_yf) >= 30:
        hist   = hist_yf
        source = "Yahoo"
        # 若字典無中文名稱，嘗試從 Yahoo 取
        if not cn_name:
            raw_name = (info_yf or {}).get("longName","") or (info_yf or {}).get("shortName","")
            cn_name  = raw_name  # 先用英文名，等下補
    else:
        print(f"Yahoo失敗→", end=" ")
        # Yahoo 失敗：嘗試 TWSE / TPEx Open API
        hist_tw = fetch_twse_history(code, is_otc=is_otc)
        if hist_tw is not None:
            hist   = hist_tw
            source = "TWSE" if not is_otc else "TPEx"
        else:
            print(f"TWSE失敗→", end=" ")
            # 再試 FinMind
            hist_fm = fetch_finmind_history(code)
            if hist_fm is not None:
                hist   = hist_fm
                source = "FinMind"
            else:
                print(f"FinMind失敗→跳過")
                _data_cache[symbol] = None
                return None

    # ── Step 3：計算日K技術指標 ──
    ind = calc_indicators(hist)
    if ind is None:
        print(f"指標計算失敗→跳過")
        _data_cache[symbol] = None
        return None

    # ── Step 3b：計算60分鐘K線 666戰法訊號 ──
    sig666 = calc_666_signal(symbol)

    # ── Step 4：即時價格補強（TWSE/TPEx API）──
    live = None
    if not is_otc:
        live = fetch_twse_price(code)
    else:
        live = fetch_tpex_price(code)

    if live and live.get("price", 0) > 0:
        ind["price"] = live["price"]
        if not cn_name and live.get("name"):
            cn_name = live["name"]

    if not cn_name:
        # Fugle 最後嘗試取名稱
        fg = fetch_fugle_price(code)
        if fg and fg.get("name"):
            cn_name = fg["name"]
        elif fg and fg.get("price", 0) > 0:
            ind["price"] = fg["price"]

    # 最終 fallback：用代號當名稱
    if not cn_name:
        cn_name = code

    # ── Step 5：基本面資料（多來源合併）──
    roe        = 0.0
    pe         = 0.0
    debt_ratio = 0.0
    eps_growth = 0.0
    sector     = "未知"
    market_cap = 0
    tp_low = tp_high = tp_mean = tp_median = None
    analyst_count  = 0
    recommend_str  = "無評級"

    # 先用 Yahoo 基本面（若有）
    if info_yf:
        roe        = safe_float(info_yf.get("returnOnEquity", 0)) * 100
        pe         = safe_float(info_yf.get("trailingPE", 0))
        debt_ratio = safe_float(info_yf.get("debtToEquity", 0))
        eps_fwd    = safe_float(info_yf.get("forwardEps", 0))
        eps_trail  = safe_float(info_yf.get("trailingEps", 0))
        sector     = info_yf.get("sector") or "未知"
        market_cap = info_yf.get("marketCap") or 0
        tp_low     = info_yf.get("targetLowPrice")  or None
        tp_high    = info_yf.get("targetHighPrice") or None
        tp_mean    = info_yf.get("targetMeanPrice") or None
        tp_median  = info_yf.get("targetMedianPrice") or None
        analyst_count = info_yf.get("numberOfAnalystOpinions") or 0
        rec_key    = info_yf.get("recommendationKey","")
        rec_map    = {"strong_buy":"強力買進","buy":"買進","hold":"持有","underperform":"表現落後","sell":"賣出","":"無評級"}
        recommend_str = rec_map.get(rec_key, rec_key)
        if eps_fwd and eps_trail and eps_trail != 0:
            eps_growth = round((eps_fwd - eps_trail) / abs(eps_trail) * 100, 1)

    # FinMind 基本面補強
    fm_fund = fetch_finmind_fundamentals(code)
    if fm_fund.get("roe") and roe == 0:
        roe = fm_fund["roe"]

    # Alpha Vantage 基本面補強
    av_fund = fetch_alpha_fundamentals(code)
    if av_fund.get("roe")        and roe == 0:        roe = av_fund["roe"]
    if av_fund.get("pe")         and pe == 0:         pe  = av_fund["pe"]
    if av_fund.get("debt_ratio") and debt_ratio == 0: debt_ratio = av_fund["debt_ratio"]

    price = ind["price"]
    upside_low  = round((tp_low  / price - 1) * 100, 1) if tp_low  and price else None
    upside_high = round((tp_high / price - 1) * 100, 1) if tp_high and price else None
    upside_mean = round((tp_mean / price - 1) * 100, 1) if tp_mean and price else None

    result = {
        "symbol":        symbol,
        "code":          code,
        "market":        market,
        "name":          cn_name,
        "sector":        sector,
        "groups":        CODE_TO_GROUP.get(code, []),
        "data_source":   source,
        # 技術面（日K）
        "price":         round(price, 1),
        "K":             ind["K"],
        "D":             ind["D"],
        "DIF":           ind["DIF"],
        "DEA":           ind["DEA"],
        "MACD_bar":      ind["MACD_bar"],
        "macd_cross":    ind["macd_cross"],
        "macd_near":     ind["macd_near"],
        "volume":        ind["volume"],
        "vol_ratio":     ind.get("vol_ratio", 0),
        "ma5":           ind.get("ma5", 0),
        "ma10":          ind.get("ma10", 0),
        "ma20":          ind.get("ma20", 0),
        "ma60":          ind.get("ma60", 0),
        # 底部型態
        "bottom_signal": ind.get("bottom_signal", False),
        "bottom_type":   ind.get("bottom_type", ""),
        # 主力/外資/融資成本
        "inst_cost":           ind.get("inst_cost", 0),
        "foreign_cost":        ind.get("foreign_cost", 0),
        "margin_cost":         ind.get("margin_cost", 0),
        "below_inst_cost":     ind.get("below_inst_cost", False),
        "below_foreign_cost":  ind.get("below_foreign_cost", False),
        "below_margin_cost":   ind.get("below_margin_cost", False),
        "inst_cost_gap":       ind.get("inst_cost_gap", 0),
        "foreign_cost_gap":    ind.get("foreign_cost_gap", 0),
        "margin_cost_gap":     ind.get("margin_cost_gap", 0),
        # 帶量突破20日線
        "vol_break_ma20":  ind.get("vol_break_ma20", False),
        "vol_above_ma20":  ind.get("vol_above_ma20", False),
        "body_pct":        ind.get("body_pct", 0),
        "above_ma20":      ind.get("above_ma20", False),
        "is_heavy_vol":    ind.get("is_heavy_vol", False),
        # 三線聚集（日K）
        "ma_converge_day": ind.get("ma_converge_day", False),
        "ma_conv_pct":     ind.get("ma_conv_pct", 0.0),
        # ── 666戰法（60分鐘K線三條件） ──
        "signal_666":       sig666.get("signal_666", False),
        "ma5_60min":        sig666.get("ma5_60min", 0.0),
        "ma20_60min":       sig666.get("ma20_60min", 0.0),
        "ma60_60min":       sig666.get("ma60_60min", 0.0),
        "price_60min":      sig666.get("price_60min", 0.0),
        "above_60ma":       sig666.get("above_60ma", False),
        "kd60_K":           sig666.get("kd60_K", 0.0),
        "kd60_D":           sig666.get("kd60_D", 0.0),
        "kd60_golden":      sig666.get("kd60_golden", False),
        "kd60_k_above50":   sig666.get("kd60_k_above50", False),
        "ma5_cross_ma60":   sig666.get("ma5_cross_ma60", False),
        "ma5_above_ma60":   sig666.get("ma5_above_ma60", False),
        # 基本面
        "roe":           round(roe, 1),
        "pe":            round(pe, 1),
        "debt_ratio":    round(debt_ratio, 1),
        "eps_growth":    eps_growth,
        "market_cap":    market_cap,
        # 法人目標價
        "tp_low":        round(tp_low, 1)    if tp_low    else None,
        "tp_high":       round(tp_high, 1)   if tp_high   else None,
        "tp_mean":       round(tp_mean, 1)   if tp_mean   else None,
        "tp_median":     round(tp_median, 1) if tp_median else None,
        "upside_low":    upside_low,
        "upside_high":   upside_high,
        "upside_mean":   upside_mean,
        "analyst_count": analyst_count,
        "recommend":     recommend_str,
    }

    print(f"✓ [{source}] {cn_name} K={ind['K']} ROE={round(roe,1)}%")
    _data_cache[symbol] = result
    return result


def score_stock(d):
    s = 0
    # 基本面（40分）
    if   d["roe"] > 25: s += 20
    elif d["roe"] > 15: s += 12
    elif d["roe"] > 8:  s += 5
    if   0 < d["pe"] < 15: s += 10
    elif 0 < d["pe"] < 25: s += 5
    if   d["debt_ratio"] < 30: s += 10
    elif d["debt_ratio"] < 50: s += 5

    # 技術面 KD（20分）
    if   d["K"] < 20: s += 20
    elif d["K"] < 30: s += 14
    elif d["K"] < 40: s += 6

    # MACD（20分）
    if   d["macd_cross"]: s += 20
    elif d["macd_near"]:  s += 12

    # 底部型態（15分）
    if d.get("bottom_signal"):
        bt = d.get("bottom_type","")
        if bt == "W底":            s += 15
        elif bt == "圓底":         s += 13
        elif bt == "均線糾結翻揚": s += 12
        elif bt == "箱型突破":     s += 10

    # 主力/外資成本（10分）
    if d.get("below_inst_cost")    and d.get("inst_cost_gap",0)    > 3: s += 5
    if d.get("below_foreign_cost") and d.get("foreign_cost_gap",0) > 3: s += 5

    # 帶量突破20日線（15分）
    if   d.get("vol_break_ma20"): s += 15
    elif d.get("vol_above_ma20"): s += 8

    # 666戰法（60分鐘KD+MA60）（12分）
    if d.get("signal_666"): s += 12

    # 三線聚集（日K MA5/20/60）（10分）
    if d.get("ma_converge_day"):
        pct = d.get("ma_conv_pct", 3.0)
        if pct < 1.0:   s += 10   # 極度聚集
        elif pct < 2.0: s += 7
        else:           s += 4

    return min(s, 100)

def build_tags(d, matched):
    tags = []
    # KD
    if   d["K"] < 20: tags.append("KD極低")
    elif d["K"] < 30: tags.append("KD超賣")
    # MACD
    if   d["macd_cross"]: tags.append("MACD黃金交叉")
    elif d["macd_near"]:  tags.append("MACD即將翻正")
    # 底部型態
    if d.get("bottom_signal") and d.get("bottom_type"):
        tags.append(f"底部:{d['bottom_type']}")
    # 主力/外資/融資成本
    if d.get("below_inst_cost"):    tags.append(f"低於主力成本-{d.get('inst_cost_gap',0)}%")
    if d.get("below_foreign_cost"): tags.append(f"低於外資成本-{d.get('foreign_cost_gap',0)}%")
    if d.get("below_margin_cost"):  tags.append(f"低於融資成本-{d.get('margin_cost_gap',0)}%")
    # 帶量突破
    if d.get("vol_break_ma20"):  tags.append("帶量突破20日線")
    elif d.get("vol_above_ma20"):tags.append("帶量站上20日線")

    # 三線聚集（日K）
    if d.get("ma_converge_day"):
        pct = d.get("ma_conv_pct", 0)
        tags.append(f"📐三線聚集{pct}%")

    # 666戰法
    if d.get("signal_666"):
        tags.append("✨666戰法成立")
    elif d.get("above_60ma") and d.get("kd60_golden") and not d.get("ma5_cross_ma60"):
        tags.append("666戰法待③5MA金叉")
    elif d.get("above_60ma") and d.get("ma5_cross_ma60") and not d.get("kd60_golden"):
        tags.append("666戰法待②KD金叉")
    elif d.get("above_60ma") and not d.get("kd60_golden") and not d.get("ma5_cross_ma60"):
        tags.append("60分收盤站上60MA")
    # 基本面
    if d["roe"] > 20:        tags.append("高ROE")
    if d["debt_ratio"] < 30: tags.append("低負債")
    if d["eps_growth"] > 10: tags.append("EPS高成長")
    if d["market"] == "上櫃": tags.append("上櫃")
    src = d.get("data_source","")
    if src: tags.append(f"來源:{src}")
    for g in d["groups"][:2]:
        tags.append(g)
    return tags


# =====================================================
#  Flask 路由
# =====================================================
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/groups")
def api_groups():
    return jsonify({"groups": list(GROUPS.keys())})

@app.route("/api/scan")
def scan():
    filter_group = request.args.get("group","")
    print(f"\n===== 掃描（{filter_group or '全部'}）— 至少 2 個條件符合才列出 =====")

    target = list(dict.fromkeys(
        s for s in (GROUPS.get(filter_group, WATCHLIST) if filter_group else WATCHLIST)
        if is_valid_symbol(s)
    ))

    results = []
    skipped = []

    for symbol in target:
        data = get_stock_data(symbol)
        time.sleep(0.3)

        if data is None:
            skipped.append(symbol)
            continue

        kd_ok       = data["K"] < 30
        macd_ok     = data["macd_cross"] or data["macd_near"]
        roe_ok      = data["roe"] > 8
        bottom_ok   = data.get("bottom_signal", False)
        cost_ok     = data.get("below_inst_cost", False) or data.get("below_foreign_cost", False)
        volbreak_ok = data.get("vol_break_ma20", False) or data.get("vol_above_ma20", False)
        sig666_ok   = data.get("signal_666", False)
        maconv_ok   = data.get("ma_converge_day", False)

        matched = []
        if kd_ok:       matched.append("kd")
        if macd_ok:     matched.append("macd")
        if roe_ok:      matched.append("roe")
        if bottom_ok:   matched.append("bottom")
        if cost_ok:     matched.append("cost")
        if volbreak_ok: matched.append("volbreak")
        if sig666_ok:   matched.append("sig666")
        if maconv_ok:   matched.append("maconv")

        # ── 至少符合 2 個條件才列出 ──
        if len(matched) >= 2:
            data["matched"]       = matched
            data["matched_count"] = len(matched)
            data["score"]         = score_stock(data)
            data["tags"]          = build_tags(data, matched)
            data["macd_status"]   = (
                "DIF已上穿DEA，黃金交叉確認" if data["macd_cross"]
                else ("DIF差距縮小，即將交叉" if data["macd_near"] else "觀察中")
            )
            results.append(data)

    results.sort(key=lambda x: (x["matched_count"], x["score"]), reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    # ── 依族群分類 ──
    # 建立族群 → 股票列表的對照
    group_map = {}   # { 族群名稱: [stock, ...] }
    no_group  = []   # 不屬於任何族群

    for stock in results:
        groups = stock.get("groups", [])
        if groups:
            primary = groups[0]   # 取第一個族群為主族群
            if primary not in group_map:
                group_map[primary] = []
            group_map[primary].append(stock)
        else:
            no_group.append(stock)

    if no_group:
        group_map["其他"] = no_group

    # 每個族群內按評分排序
    for g in group_map:
        group_map[g].sort(key=lambda x: (x["matched_count"], x["score"]), reverse=True)

    # 轉成有序列表供前端使用
    grouped = [
        {"group": g, "stocks": group_map[g], "count": len(group_map[g])}
        for g in group_map
    ]
    # 族群按所含股票數量排序（多的排前）
    grouped.sort(key=lambda x: x["count"], reverse=True)

    print(f"===== 完成：符合 {len(results)} / 掃描 {len(target)} / 跳過 {len(skipped)} / 族群 {len(grouped)} 個 =====\n")
    return jsonify({
        "success":  True,
        "count":    len(results),
        "stocks":   results,          # 完整清單（保留向下相容）
        "grouped":  grouped,          # 依族群分類的結果
        "scanned":  len(target),
        "skipped":  len(skipped),
        "group":    filter_group or "全部",
        "min_conditions": 2,
    })


@app.route("/api/targets")
def targets():
    filter_group = request.args.get("group","")
    print(f"\n===== 法人目標價掃描（{filter_group or '全部'}）=====")

    target = list(dict.fromkeys(
        s for s in (GROUPS.get(filter_group, WATCHLIST) if filter_group else WATCHLIST)
        if is_valid_symbol(s)
    ))

    results = []
    for symbol in target:
        data = get_stock_data(symbol)
        time.sleep(0.3)
        if data is None:
            continue
        mid = None
        if data["tp_low"] and data["tp_high"]:
            mid = round((data["tp_low"] + data["tp_high"]) / 2, 1)
        results.append({
            "symbol":        data["symbol"],
            "code":          data["code"],
            "market":        data["market"],
            "name":          data["name"],
            "groups":        data["groups"],
            "price":         data["price"],
            "tp_low":        data["tp_low"],
            "tp_high":       data["tp_high"],
            "tp_mean":       data["tp_mean"],
            "tp_mid":        mid,
            "upside_low":    data["upside_low"],
            "upside_high":   data["upside_high"],
            "upside_mean":   data["upside_mean"],
            "analyst_count": data["analyst_count"],
            "recommend":     data["recommend"],
            "below_mid":     (mid is not None and data["price"] < mid),
            "data_source":   data.get("data_source",""),
        })

    results.sort(key=lambda x:(0 if (x["tp_low"] or x["tp_high"]) else 1,
                                0 if x["below_mid"] else 1,
                                -(x["upside_mean"] or 0)))
    print(f"===== 目標價完成：{len(results)} 檔 =====\n")
    return jsonify({"success":True,"count":len(results),"stocks":results,
                    "scanned":len(target),"group":filter_group or "全部"})


# =====================================================
#  /api/single  — 單股即時查詢
# =====================================================
@app.route("/api/single")
def api_single():
    query = request.args.get("code", "").strip()
    if not query:
        return jsonify({"error": "請提供股票代碼或中文名稱"})

    # ── 判斷輸入：中文名稱 or 股票代碼 ──
    # 若輸入包含中文字元，視為名稱搜尋
    is_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)

    if is_chinese:
        # 模糊比對中文名稱 → 找出代碼
        matched_codes = [
            code for code, name in CHINESE_NAMES.items()
            if query in name
        ]
        if not matched_codes:
            return jsonify({"error": f"找不到包含「{query}」的股票名稱，請確認名稱或改用代碼查詢"})
        if len(matched_codes) > 1:
            # 先試完全匹配
            exact = [c for c in matched_codes if CHINESE_NAMES[c] == query]
            code = exact[0] if exact else matched_codes[0]
        else:
            code = matched_codes[0]
    else:
        code = query.upper().replace(".TW","").replace(".TWO","")

    # 判斷上市(TW) / 上櫃(TWO)
    symbol_tw  = f"{code}.TW"
    symbol_two = f"{code}.TWO"

    # 先試上市，失敗再試上櫃
    data = get_stock_data(symbol_tw)
    if data is None:
        data = get_stock_data(symbol_two)
    if data is None:
        cn = CHINESE_NAMES.get(code, "")
        label = f"{code}（{cn}）" if cn else code
        return jsonify({"error": f"找不到 {label} 的資料，請確認代碼或名稱是否正確"})

    # 計算 matched / tags / score
    kd_ok      = data["K"] < 30
    macd_ok    = data["macd_cross"] or data["macd_near"]
    roe_ok     = data["roe"] > 8
    bottom_ok  = data.get("bottom_signal", False)
    cost_ok    = data.get("below_inst_cost", False) or data.get("below_foreign_cost", False)
    volbreak_ok= data.get("vol_break_ma20", False) or data.get("vol_above_ma20", False)
    sig666_ok  = data.get("signal_666", False)
    maconv_ok  = data.get("ma_converge_day", False)

    matched = []
    if kd_ok:       matched.append("kd")
    if macd_ok:     matched.append("macd")
    if roe_ok:      matched.append("roe")
    if bottom_ok:   matched.append("bottom")
    if cost_ok:     matched.append("cost")
    if volbreak_ok: matched.append("volbreak")
    if sig666_ok:   matched.append("sig666")
    if maconv_ok:   matched.append("maconv")

    data["matched"]       = matched
    data["matched_count"] = len(matched)
    data["score"]         = score_stock(data)
    data["tags"]          = build_tags(data, matched)

    return jsonify(data)


if __name__ == "__main__":
    print("=" * 65)
    print("  🌊 鑽石股雷達後端 v6 啟動中...")
    print(f"  📋 掃描清單：{len(WATCHLIST)} 檔（上市+上櫃）")
    print(f"  🗂️  族群數量：{len(GROUPS)} 個")
    print(f"  📡 資料來源：TWSE/TPEx Open API + Yahoo Finance + FinMind + Fugle + Alpha Vantage")
    print(f"  ✅ 篩選邏輯：至少 2 個條件符合才列出（KD / MACD / ROE / 底部型態 / 成本價 / 帶量突破）")
    print(f"  📊 技術指標：日K線 — KD、MACD、均線、底部型態、VWAP成本、帶量突破20MA")
    print()
    if not FINMIND_TOKEN:
        print("  ⚠️  FinMind Token 未設定（可在 server.py 頂部填入）")
    if not FUGLE_API_KEY:
        print("  ⚠️  Fugle API Key 未設定（可在 server.py 頂部填入）")
    if not ALPHA_VANTAGE_KEY:
        print("  ⚠️  Alpha Vantage Key 未設定（可在 server.py 頂部填入）")
    print()
    print("  本機開啟：http://localhost:5000")
    print("=" * 65)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, port=port, host="0.0.0.0")
