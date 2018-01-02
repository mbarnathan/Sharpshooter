import asyncio
import logging
import sys

import ccxt.async as ccxt
from ccxt import RequestTimeout, ExchangeError

from src.fast_cryptopia import FastCryptopia
from src.rate_table import RateTable
from src.trade import Trade

BLACKLISTED = set([
    # Different coins, same name.
    "BAT",
    "FUEL",
    "CMT",

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


class Sharpshooter:
    def __init__(self, exchanges, starting_currency, blacklisted=None,
                 arbitrage_threshold_pcent=0.025):
        self.blacklisted = blacklisted or BLACKLISTED
        self.exchange_rates = RateTable()
        self.exchanges = exchanges
        self.starting_currency = starting_currency
        self.arbitrage_threshold = arbitrage_threshold_pcent

    def run_forever(self):
        loop = asyncio.get_event_loop()
        for exchange in self.exchanges:
            asyncio.ensure_future(self.populate_task(exchange))
        asyncio.ensure_future(self.print_complex_arbs_task())
        loop.run_forever()

    def run_once(self):
        populate = asyncio.ensure_future(
            asyncio.gather(*[self.exchange_rates.populate(exchange, blacklisted=self.blacklisted)
                             for exchange in self.exchanges]))
        asyncio.get_event_loop().run_until_complete(populate)
        return list(self.complex_arbs())

    def simple_arbs(self, from_cur, to_cur):
        return self.exchange_rates.pairwise_diffs(from_cur, to_cur)

    def complex_arbs(self):
        currency, amount = self.starting_currency
        logging.debug(f"Checking {currency} roundtrips...")
        roundtrips = self.exchange_rates.best_roundtrips(currency, amount, max_steps=3)
        roundtrips = sorted(roundtrips, key=Trade.num_exchanges)

        profitable = 0
        for index, best_conversion in enumerate(roundtrips):
            profit = Trade.profitability(best_conversion)
            if profit < self.arbitrage_threshold:
                continue

            profitable += 1
            yield (best_conversion, profit)

        logging.debug(f"Found {len(roundtrips)} {currency} roundtrips, "
                      f"{profitable} above the profit threshold")

    @staticmethod
    def print_arbs(arbs):
        for best_conversion, profit in arbs:
            print(f"{best_conversion} for {profit * 100}% profit")

    async def print_complex_arbs_task(self):
        while True:
            self.print_arbs(self.complex_arbs())
            await asyncio.sleep(1)

    async def populate_task(self, exchange):
        while True:
            try:
                await self.exchange_rates.populate(exchange, blacklisted=self.blacklisted)
            except (TimeoutError, RequestTimeout, ExchangeError) as e:
                logging.error(e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    EXCHANGES = {
        #        ccxt.bittrex({'enableRateLimit': True}),
        #        ccxt.gdax({'enableRateLimit': True}),
        #        ccxt.kraken({'enableRateLimit': True}),
        #        ccxt.poloniex({'enableRateLimit': True}),
        ##        ccxt.bitmex({'enableRateLimit': True}),
        FastCryptopia({'enableRateLimit': True}),
        #        ccxt.gemini({'enableRateLimit': True}),
        ccxt.binance({'enableRateLimit': True})
    }
    logging.basicConfig(level=logging.INFO)
    start_with = ("ETH", 10)
    arbs = Sharpshooter(EXCHANGES, start_with).run_once()
    Sharpshooter.print_arbs(arbs)
