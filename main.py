import requests
import pandas as pd
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8712983617:AAEJ0TzE8vowoQoHqUtJxRPeRKLa_GelYxY"
CHAT_ID = "-1003770571523"
API_KEY = "17de56266a444f65b9abdefbb8999865"

PARES = [
    "EUR/USD",
    "USD/JPY",
    "USD/CHF",
    "BTC/USD",
    "ETH/USD"
]

ULTIMO_SINAL = {}

# ==========================================

def enviar_mensagem(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ==========================================

def pegar_dados(par):
    url = f"https://api.twelvedata.com/time_series?symbol={par}&interval=15min&apikey={API_KEY}&outputsize=100"
    data = requests.get(url).json()

    if "values" not in data:
        return None

    df = pd.DataFrame(data["values"])
    df = df.iloc[::-1]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df

# ==========================================

def calcular_indicadores(df):
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema21"] = df["close"].ewm(span=21).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    # RSI
    delta = df["close"].diff()
    ganho = delta.clip(lower=0)
    perda = -delta.clip(upper=0)
    rs = ganho.rolling(14).mean() / perda.rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger
    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]

    # ADX simplificado (força de movimento)
    df["tr"] = df["high"] - df["low"]
    df["adx"] = df["tr"].rolling(14).mean()

    return df

# ==========================================

def gerar_sinal(df):
    ultima = df.iloc[-1]
    score = 0

    tendencia_alta = ultima["close"] > ultima["ema200"]
    tendencia_baixa = ultima["close"] < ultima["ema200"]

    # filtro de lateralização
    if ultima["adx"] < 0.002:
        return None, score

    # RSI
    if ultima["rsi"] < 35:
        score += 1
    if ultima["rsi"] > 65:
        score += 1

    # EMA cruzamento
    if ultima["ema9"] > ultima["ema21"]:
        score += 1
    if ultima["ema9"] < ultima["ema21"]:
        score += 1

    # Bollinger
    if ultima["close"] <= ultima["bb_lower"]:
        score += 1
    if ultima["close"] >= ultima["bb_upper"]:
        score += 1

    # decisão forte
    if tendencia_alta and score >= 5:
        return "CALL", score
    elif tendencia_baixa and score >= 5:
        return "PUT", score

    return None, score

# ==========================================

def montar_mensagem(par, sinal, score, preco):
    hora = datetime.now().strftime("%H:%M")

    confianca = min(95, score * 15)
    assertividade = min(90, score * 12)

    return f"""
📈 NOVO SINAL - {sinal}

📊 Ativo: {par}
⏱ Timeframe: M15
💰 Preço: {preco:.5f}

📊 Confiança: {confianca}%
✅ Assertividade: {assertividade}%

⏰ Horário: {hora}
"""

# ==========================================

def horario_valido():
    hora = datetime.now().hour
    return 8 <= hora <= 17

# entrada no início da vela
def entrada_perfeita():
    minuto = datetime.now().minute
    return minuto % 15 == 0

# ==========================================

while True:
    try:
        if not horario_valido():
            time.sleep(300)
            continue

        for par in PARES:

            df = pegar_dados(par)
            if df is None:
                continue

            df = calcular_indicadores(df)
            sinal, score = gerar_sinal(df)

            if sinal and entrada_perfeita():

                if ULTIMO_SINAL.get(par) == sinal:
                    continue

                preco = df["close"].iloc[-1]
                mensagem = montar_mensagem(par, sinal, score, preco)

                enviar_mensagem(mensagem)
                ULTIMO_SINAL[par] = sinal

        time.sleep(60)

    except Exception as e:
        print("Erro:", e)
        time.sleep(60)
