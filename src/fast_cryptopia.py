import asyncio
import itertools

import more_itertools
import time
from ccxt.async import cryptopia


class FastCryptopia(cryptopia):
    REFRESH_SECONDS = 2

    def __init__(self, *args, **kwargs):
        super(FastCryptopia, self).__init__(*args, **kwargs)
        self._order_books = None
        self._fetching = asyncio.Event()
        self._last_fetch = 0
        self.has["fetchOrderBooks"] = True

    @staticmethod
    def _convert_order_books(response):
        for data in response:
            data["Market"] = data["Market"].replace("_", "/")
            for order in itertools.chain(data["Buy"], data["Sell"]):
                order["Label"] = order["Label"].replace("_", "/")
        return response

    async def fetch_order_book(self, symbol, params={}):
        if not self._order_books or time.time() > self._last_fetch + self.REFRESH_SECONDS:
            self._fetching.clear()
            self._order_books = self.fetch_order_books(params)
            self._order_books = await self._order_books
            self._last_fetch = time.time()
            self._fetching.set()
        else:
            await self._fetching.wait()
        orderbooks = self._order_books
        book = self.parse_order_book(orderbooks[symbol], None, 'Buy', 'Sell', 'Price', 'Volume')
        return book

    async def fetch_order_books(self, params):
        await self.load_markets()
        symbols = [symbol.replace("/", "_") for symbol in self.symbols]
        result = {}
        for chunk in more_itertools.chunked(symbols, 1000):
            ids = "-".join(chunk)
            response = await self.publicGetMarketOrderGroupsIdsCount(self.extend({
                'ids': ids, "count": 55
            }, params))
            books = self._convert_order_books(response["Data"])
            result.update({data["Market"]: data for data in books})
        return result
