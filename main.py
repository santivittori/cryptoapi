# Author: Santiago Vittori
# Python API

from fastapi import FastAPI, HTTPException
import feedparser
import requests
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from datetime import datetime

app = FastAPI()

coingecko_base_url = "https://api.coingecko.com/api/v3"

app.mount("/static", StaticFiles(directory="static"), name="static")

with open("welcome_page.html", "r") as file:
    welcome_page_content = file.read()


@app.get("/", response_class=HTMLResponse)
def welcome():
    return welcome_page_content


@app.get("/cryptos")
def get_all_cryptos(skip: int = 0, limit: int = 20):
    response = requests.get(f"{coingecko_base_url}/coins/markets", params={"vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    total_cryptos = len(data)

    crypto_list = []
    for crypto in data[skip: skip + limit]:
        current_price = round(crypto["current_price"], 2)
        crypto_list.append({
            "id": crypto["id"],
            "symbol": crypto["symbol"],
            "name": crypto["name"],
            "current_price": current_price
        })

    headers = {
        "Cache-Control": "no-store, max-age=0",
        "X-Total-Count": str(total_cryptos)
    }

    return JSONResponse(content=crypto_list, headers=headers)


@app.get("/cryptos/{crypto_name}")
def get_crypto_data(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/markets",
                            params={"ids": crypto_name, "vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()

    if not data:
        raise HTTPException(status_code=404,
                            detail=f"Cryptocurrency '{crypto_name}' not found")

    crypto_info = data[0]

    current_price = round(crypto_info["current_price"], 2)

    return {
        "id": crypto_info["id"],
        "symbol": crypto_info["symbol"],
        "name": crypto_info["name"],
        "current_price": current_price,
        "volume_24h": crypto_info["total_volume"],
        "price_change_percentage_24h": crypto_info["price_change_percentage_24h"],
        "low_24h": crypto_info["low_24h"],
        "high_24h": crypto_info["high_24h"]
    }


@app.get("/cryptos/{crypto_name}/details")
def get_crypto_details(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()

    current_price = round(data["market_data"]["current_price"]["usd"], 2)

    crypto_details = {
        "name": data["name"],
        "symbol": data["symbol"],
        "description": data["description"]["en"],
        "circulating_supply": data["market_data"]["circulating_supply"],
        "total_supply": data["market_data"]["total_supply"],
        "market_cap": data["market_data"]["market_cap"]["usd"],
        "current_price": current_price,
        "ath": data["market_data"]["ath"]["usd"],
        "ath_date": data["market_data"]["ath_date"]["usd"],
        "atl": data["market_data"]["atl"]["usd"],
        "atl_date": data["market_data"]["atl_date"]["usd"],
        "links": {
            "homepage": data["links"]["homepage"][0] if data["links"]["homepage"] else None,
            "twitter": data["links"]["twitter_screen_name"],
            "reddit": data["links"]["subreddit_url"],
        }
    }

    return crypto_details


def get_formatted_news_from_url(url):
    feed = feedparser.parse(url)
    formatted_news = []

    for entry in feed.entries:
        formatted_news.append({
            "title": entry.title,
            "published": entry.published,
            "link": entry.link,
            "description": entry.description
        })

    return formatted_news


@app.get("/crypto-news")
def get_crypto_news():
    urls = [
        "https://www.fxempire.com/api/v1/en/articles/rss/news",
        "https://cointelegraph.com/rss"
    ]

    all_formatted_news = []

    for url in urls:
        formatted_news = get_formatted_news_from_url(url)
        all_formatted_news.extend(formatted_news)

    return all_formatted_news


@app.get("/average-volume/{crypto_name}")
def get_average_volume(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 30})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    volumes = [entry[1] for entry in data["total_volumes"]]
    average_volume = sum(volumes) / len(volumes)

    return {"crypto_id": crypto_name, "average_volume_30_days": round(average_volume, 2)}


@app.get("/crypto-exchanges/{crypto_name}")
def get_crypto_exchanges(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    exchanges = data.get("tickers")
    if not exchanges:
        raise HTTPException(status_code=404, detail="Exchange data not available for this cryptocurrency")

    exchange_info = []
    for exchange in exchanges:
        exchange_info.append({
            "exchange_name": exchange["market"]["name"],
            "base": exchange["base"],
            "target": exchange["target"],
            "trade_url": exchange["trade_url"]
        })

    return exchange_info


def calculate_exponential_moving_average(prices, window):
    weights = np.exp(np.linspace(-1., 0., window))
    weights /= weights.sum()
    ema = np.convolve(prices, weights, mode="full")[:len(prices)]
    return ema


@app.get("/short-term/{crypto_name}")
def get_short_term_signal(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 1})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    prices = [entry[1] for entry in data["prices"]]
    ema_20 = calculate_exponential_moving_average(prices, window=20)
    current_price = prices[-1]

    if current_price > ema_20[-1]:
        signal = "long"
        position = "price above EMA 20"
    else:
        signal = "short"
        position = "price below EMA 20"

    return {"signal": signal, "position": position}


@app.get("/long-term/{crypto_name}")
def get_long_term_signal(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 1})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    prices = [entry[1] for entry in data["prices"]]
    ema_200 = calculate_exponential_moving_average(prices, window=200)
    current_price = prices[-1]

    if current_price > ema_200[-1]:
        signal = "long"
        position = "price above EMA 200"
    else:
        signal = "short"
        position = "price below EMA 200"

    return {"signal": signal, "position": position}


def format_timestamp(timestamp):
    dt_object = datetime.fromtimestamp(timestamp / 1000)
    return dt_object.strftime("%Y-%m-%d %H:%M:%S")


@app.get("/historical-prices/{crypto_name}")
def get_historical_prices(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 30})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    price_data = [{"timestamp": format_timestamp(entry[0]), "price": round(entry[1], 2)} for entry in data["prices"]]

    price_data.reverse()

    return {"price_data": price_data}


@app.get("/correlation-analysis/{crypto_name}")
def get_correlation_analysis(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 180})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    prices = [entry[1] for entry in data["prices"]]

    btc_data = requests.get(f"{coingecko_base_url}/coins/bitcoin/market_chart", params={
        "vs_currency": "usd", "days": 180}).json()
    btc_prices = [entry[1] for entry in btc_data["prices"]]

    eth_data = requests.get(f"{coingecko_base_url}/coins/ethereum/market_chart", params={
        "vs_currency": "usd", "days": 180}).json()
    eth_prices = [entry[1] for entry in eth_data["prices"]]

    correlation_with_btc = np.corrcoef(prices, btc_prices)[0, 1]
    correlation_with_eth = np.corrcoef(prices, eth_prices)[0, 1]

    return {
        "crypto_id": crypto_name,
        "correlation_with_btc": correlation_with_btc,
        "correlation_with_eth": correlation_with_eth
    }


def calculate_volatility(prices):
    returns = np.diff(np.log(prices))
    volatility = np.std(returns) * np.sqrt(252)  # 252 días de trading en un año
    return volatility


@app.get("/volatility-heatmap/{crypto_name}")
def get_volatility_heatmap(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/markets", params={"vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()

    # Check if the provided crypto_name exists
    if not any(crypto["id"] == crypto_name for crypto in data):
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")

    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/market_chart", params={
        "vs_currency": "usd", "days": 90})  # Reduce interval to 90 days

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining price data")

    price_data = [entry[1] for entry in response.json()["prices"]]
    volatility = calculate_volatility(price_data)

    return {"crypto_name": crypto_name, "volatility": volatility}


@app.get("/social-sentiment-analysis/{crypto_name}")
def get_social_sentiment_analysis(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()

    if "sentiment_votes_up_percentage" not in data or "sentiment_votes_down_percentage" not in data:
        raise HTTPException(status_code=404, detail="Sentiment data not available")

    sentiment_votes_up_percentage = data["sentiment_votes_up_percentage"]
    sentiment_votes_down_percentage = data["sentiment_votes_down_percentage"]

    sentiment_score = sentiment_votes_up_percentage - sentiment_votes_down_percentage

    sentiment = "neutral"
    if sentiment_score > 0.1:
        sentiment = "positive"
    elif sentiment_score < -0.1:
        sentiment = "negative"

    return {"crypto_id": crypto_name, "sentiment": sentiment, "sentiment_score": sentiment_score}


@app.get("/profit-loss-calculator")
def calculate_profit_loss(crypto_name: str = None, amount: float = None, purchase_price: float = None,
                          operation: str = None):
    if not (crypto_name and amount and purchase_price and operation):
        example_message = \
            "Example: /profit-loss-calculator?crypto_name=bitcoin&amount=1&purchase_price=50000&operation=long"
        raise HTTPException(status_code=400,
                            detail="Please provide the required parameters. " + example_message)

    response = requests.get(f"{coingecko_base_url}/coins/markets", params={"vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    current_price = None

    for crypto in data:
        if crypto["id"] == crypto_name:
            current_price = crypto["current_price"]
            break

    if current_price is None:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")

    profit_loss = (current_price - purchase_price) * amount
    if operation == "short":
        profit_loss = -profit_loss

    profit_loss_status = "profit" if profit_loss >= 0 else "loss"
    profit_loss = abs(profit_loss) * amount  # Multiply by amount of cryptocurrency bought

    return {"crypto_name": crypto_name, "operation": operation, "current_price": current_price,
            "profit_loss_status": profit_loss_status, "profit_loss_value": profit_loss}
