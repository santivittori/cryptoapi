# Author: Santiago Vittori
# Python API

from fastapi import FastAPI, HTTPException
import requests
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from datetime import datetime
import asyncio


app = FastAPI()

coingecko_base_url = "https://api.coingecko.com/api/v3"

crypto_prices = {}

app.mount("/static", StaticFiles(directory="static"), name="static")

with open("welcome_page.html", "r") as file:
    welcome_page_content = file.read()


async def update_crypto_prices():
    while True:
        try:
            response = requests.get(f"{coingecko_base_url}/coins/markets", params={"vs_currency": "usd"})
            if response.status_code == 200:
                data = response.json()
                for crypto in data:
                    current_price = round(crypto["current_price"], 2)
                    crypto_prices[crypto["id"]] = current_price
        except Exception as e:
            print("Error updating crypto prices:", str(e))

        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_crypto_prices())


@app.get("/", response_class=HTMLResponse)
def welcome():
    return welcome_page_content


@app.get("/cryptos")
def get_all_cryptos():
    response = requests.get(f"{coingecko_base_url}/coins/markets", params={"vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()
    crypto_list = []

    for crypto in data:
        current_price = round(crypto["current_price"], 2)
        crypto_list.append({
            "id": crypto["id"],
            "symbol": crypto["symbol"],
            "name": crypto["name"],
            "current_price": current_price
        })

    return JSONResponse(content=crypto_list, headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/cryptos/{crypto_name}")
def get_crypto_data(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/markets",
                            params={"ids": crypto_name, "vs_currency": "usd"})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining cryptocurrency data")

    data = response.json()

    if not data:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")

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


@app.get("/social-sentiment-analysis/{crypto_name}")
def get_social_sentiment_analysis(crypto_name: str):
    response = requests.get(f"{coingecko_base_url}/coins/{crypto_name}/social_stats")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error when obtaining social stats")

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
