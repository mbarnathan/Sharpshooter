import asyncio
import sys
from decimal import getcontext

import ccxt.async as ccxt
from more_itertools import first

from src.rate_table import RateTable


def main(argv):
    EXCHANGES = {
        ccxt.bittrex(),
        ccxt.gdax(),
        ccxt.kraken(),
        ccxt.poloniex(),
        ccxt.bitmex(),
        ccxt.cryptopia(),
        ccxt.gemini(),
        ccxt.binance()
    }

    ARBITRAGE_THRESHOLD_PCENT = 0.02

    getcontext().prec = 8
    exchange_rates = RateTable()

    async def populate_with_tickers(exchange, rates):
        while True:
            tickers = await exchange.fetch_tickers()
            for pair, data in tickers.items():
                coin1, coin2 = pair.split("/", 1)
                if not coin1 or not coin2 or not data["bid"] or not data["ask"]:
                    continue

                if coin1 not in rates:
                    rates[coin1] = {}

                if coin2 not in rates:
                    rates[coin2] = {}

                rates[coin1][coin2] = data["ask"]
                rates[coin2][coin1] = 1 / data["bid"]
            await asyncio.sleep(1)

    async def simple_arbs(exchange_rates):
        while True:
            diffs, percentages = exchange_rates.pairwise_diffs("BTC", "USD")
            print(diffs)
            await asyncio.sleep(1)

    async def complex_arbs(exchange_rates):
        while True:
            for index, best_conversion in enumerate(exchange_rates.best_conversions("USD", "USD")):
                if index >= 5:
                    break

                profit = RateTable.profitability(best_conversion)
                if profit < ARBITRAGE_THRESHOLD_PCENT:
                    # It's sorted, all of the below will be worse.
                    break
                print(f"{best_conversion} for {profit * 100}% profit")
            print()
            await asyncio.sleep(1)

    loop = asyncio.get_event_loop()
    for exchange in EXCHANGES:
        if exchange.hasFetchTickers:
            rates_on_exchange = {}
            exchange_rates[exchange.name] = rates_on_exchange
            asyncio.ensure_future(populate_with_tickers(exchange, rates_on_exchange))

    #asyncio.ensure_future(simple_arbs(exchange_rates))
    asyncio.ensure_future(complex_arbs(exchange_rates))
    loop.run_forever()

#        print (symbol, exchange.fetch_ohlcv (symbol, '1d')) # one day
    #print(exchange.fetch_tickers()) # all tickers indexed by their symbols


def fetchTickers(exchange):
    pass


if __name__ == "__main__":
    main(sys.argv)