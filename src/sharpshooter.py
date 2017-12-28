import asyncio
import logging
import sys
from decimal import getcontext

import ccxt.async as ccxt
from ccxt import RequestTimeout, ExchangeError

from src.fast_cryptopia import fast_cryptopia
from src.rate_table import RateTable
from src.trade import Trade


def main(argv):
    logging.basicConfig(level=logging.DEBUG)

    EXCHANGES = {
#        ccxt.bittrex({'enableRateLimit': True}),
#        ccxt.gdax({'enableRateLimit': True}),
#        ccxt.kraken({'enableRateLimit': True}),
#        ccxt.poloniex({'enableRateLimit': True}),
##        ccxt.bitmex({'enableRateLimit': True}),
        fast_cryptopia({'enableRateLimit': True}),
#        ccxt.gemini({'enableRateLimit': True}),
#        ccxt.binance({'enableRateLimit': True})
    }

    BLACKLISTED = set([
        "BAT",  # Different coins, same name.
        "FUEL",  # Different coins, same name.
        
        # Non-USD fiat.
        "CAD",
        "GBP",
        "EUR",
        "JPY",
        "KRW",
        "CNY",
        "NZD",
        "AUD"
    ])

    ARBITRAGE_THRESHOLD_PCENT = 0.025

    getcontext().prec = 8
    exchange_rates = RateTable()

    async def populate_with_tickers(exchange, rates):
        logging.info(f"Initializing {exchange}...")
        for attempt in range(5):
            try:
                await exchange.load_markets()
                break
            except RequestTimeout:
                pass

        while True:
            try:
                #if exchange.hasFetchTickers:
                #    tickers = await exchange.fetch_tickers()
                #else:
                #    tickers = [exchange.fetch_ticker(symbol) for symbol in exchange.symbols]
                #    tickers = await asyncio.gather(*tickers, return_exceptions=True)
                #    tickers = {sym["symbol"]: sym for sym in tickers}

                pairs = [symbol for symbol in exchange.symbols
                         if symbol and "/" in symbol
                         and symbol.split("/", 1)[0] not in BLACKLISTED
                         and symbol.split("/", 1)[1] not in BLACKLISTED]

                logging.debug(f"Loading {len(pairs)} markets at {exchange}...")
                books = [exchange.fetch_l2_order_book(symbol) for symbol in pairs]
                books = await asyncio.gather(*books, return_exceptions=True)
                books = {symbol: book for symbol, book in zip(pairs, books)}

                if not rates:
                    logging.info(f"Loaded {len(books)} markets at {exchange}.")

                for pair, data in books.items():
                    coin1, coin2 = pair.split("/", 1)
                    try:
                        if not coin1 or not coin2 or not data["bids"] or not data["asks"]:
                            continue
                    except TypeError as e:
                        logging.warning(f"{e} when processing {pair}; data is {data}")
                        continue

                    if coin1 not in rates:
                        rates[coin1] = {}

                    if coin2 not in rates:
                        rates[coin2] = {}

                    # e.g. ETH/USD:
                    # coin1 = ETH
                    # coin2 = USD
                    # The table is "from -> to", so "I have ETH and I want USD" means selling,
                    # which means placing an order at the bid to get a fill.
                    # Going the other way entails buying at 1 / the ask in USD.
                    rates[coin1][coin2] = data["bids"]
                    rates[coin2][coin1] = [(1 / ask, volume) for ask, volume in data["asks"]]
            except (TimeoutError, RequestTimeout, ExchangeError) as e:
                logging.error(e)

            await asyncio.sleep(1)

    async def simple_arbs(exchange_rates):
        while True:
            diffs, percentages = exchange_rates.pairwise_diffs("LTC", "USD")
            print(diffs)
            await asyncio.sleep(1)

    async def complex_arbs(exchange_rates):
        while True:
            roundtrips = exchange_rates.best_roundtrips("ETH", 10, max_steps=3)
            roundtrips = sorted(roundtrips, key=Trade.num_exchanges)

            for index, best_conversion in enumerate(roundtrips):
                profit = Trade.profitability(best_conversion)
                if profit < ARBITRAGE_THRESHOLD_PCENT:
                    continue

                print(f"{best_conversion} for {profit * 100}% profit")
            print()
            await asyncio.sleep(1)

    loop = asyncio.get_event_loop()
    for exchange in EXCHANGES:
        rates_on_exchange = {}
        exchange_rates[exchange.name] = rates_on_exchange
        asyncio.ensure_future(populate_with_tickers(exchange, rates_on_exchange))

    # asyncio.ensure_future(simple_arbs(exchange_rates))
    asyncio.ensure_future(complex_arbs(exchange_rates))
    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv)