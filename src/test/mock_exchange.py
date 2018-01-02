# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime

from ccxt.async import Exchange


class MockExchange(Exchange):
    """Mock exchange that can be used to test order book functionality."""

    def __init__(self, *args, **kwargs):
        super(MockExchange, self).__init__(*args, **kwargs)
        recursive_dict = lambda: defaultdict(recursive_dict)
        self.books = defaultdict(recursive_dict)
        self.has["fetchOrderBooks"] = True

    def add_bid(self, symbol, price, volume):
        to_cur, from_cur = symbol.split("/")
        bids = self.books[from_cur][to_cur].get("bids", [])
        self._add_order(bids, price, volume)
        bids = sorted(bids, reverse=True)
        self.books[from_cur][to_cur]["bids"] = bids
        return bids

    def add_ask(self, symbol, price, volume):
        to_cur, from_cur = symbol.split("/")
        asks = self.books[from_cur][to_cur].get("asks", [])
        self._add_order(asks, price, volume)
        asks = sorted(asks, reverse=False)
        self.books[from_cur][to_cur]["asks"] = asks
        return asks

    def _add_order(self, existing_orders, price, volume):
        for order in existing_orders:
            if order[0] == price:
                order[1] += volume
                assert order[1] >= 0
                break
        else:
            order = [price, volume]
            assert order[1] >= 0
            existing_orders.append(order)
        return order

    def describe(self):
        return self.deep_extend(super(MockExchange, self).describe(), {
            'id': 'mock',
            'name': 'Mock Exchange',
            'countries': 'US',
            'rateLimit': 1,
            'version': 'v1',
            'hasCORS': False,
            'urls': {
                'logo': 'about:blank',
                'api': 'about:blank',
                'www': 'about:blank',
                'doc': 'about:blank',
            },
        })

    def set_markets(self, markets, currencies=None):
        return self.symbols

    @property
    def symbols(self):
        def symbol_iter():
            for from_cur, pair in self.books.items():
                for to_cur in pair.keys():
                    yield f"{to_cur}/{from_cur}"
        return list(symbol_iter())

    async def fetch_markets(self):
        return [{
            'id': index,
            'symbol': symbol,
            'base': symbol.split("/")[1],
            'quote': symbol.split("/")[0],
            'info': {},
            'taker': 0.0025  # TODO(mb): Test fee info when needed.
        } for index, symbol in enumerate(self.symbols)]

    async def fetch_order_book(self, symbol, params={}):
        await self.load_markets()
        quote, base = symbol.split("/")
        orderbook = self.books.get(base, {}).get(quote, {}).copy()
        return self.parse_order_book(orderbook, None, 'bids', 'asks', 0, 1)

    async def fetch_ticker(self, symbol, params={}):
        await self.load_markets()
        orderbook = self.fetch_order_book(symbol, params)
        best_bid = orderbook["bids"][0] if orderbook["bids"] else None
        best_ask = orderbook["asks"][0] if orderbook["asks"] else None

        timestamp = datetime.now()
        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'datetime': self.iso8601(timestamp),
            'high': None,
            'low': None,
            'bid': best_bid[0],
            'ask': best_ask[0],
            'vwap': None,
            'open': None,
            'close': None,
            'first': None,
            'last': best_ask[0],
            'change': None,
            'percentage': None,
            'average': None,
            'baseVolume': None,
            'quoteVolume': None,
            'info': orderbook,
        }
