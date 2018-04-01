import asyncio
import collections
import itertools
import logging
from collections import OrderedDict, defaultdict
from typing import Dict, Tuple

from ccxt import RequestTimeout
from more_itertools import nth

from src.trade import Trade


class RateTable(collections.UserDict):
    SYNONYMS = {
        "XBT": "BTC",
        "BCC": "BCH",
    }

    SYNONYMS.update({v: k for k, v in SYNONYMS.items()})

    async def populate(self, exchange, blacklisted=None):
        if not blacklisted:
            blacklisted = set()

        marginal = self.get(exchange.name)
        if marginal is None:
            logging.info(f"Initializing {exchange}...")
            marginal = {}
            self[exchange.name] = marginal
            for attempt in range(5):
                try:
                    await exchange.load_markets()
                    break
                except RequestTimeout:
                    pass

        pairs = [symbol for symbol in exchange.symbols
                 if symbol and "/" in symbol
                 and symbol.split("/", 1)[0] not in blacklisted
                 and symbol.split("/", 1)[1] not in blacklisted]

        for attempt in range(5):
            try:
                if not exchange.hasFetchTickers \
                        or len(pairs) <= 10 or exchange.has.get("fetchOrderBooks", False):
                    logging.debug(f"Loading {len(pairs)} markets by book at {exchange}...")
                    books = [exchange.fetch_l2_order_book(symbol) for symbol in pairs]
                    books = await asyncio.gather(*books, return_exceptions=True)
                    books = {symbol: book for symbol, book in zip(pairs, books)}
                else:
                    logging.debug(f"Loading {len(pairs)} markets by tickers at {exchange}...")
                    tickers = await exchange.fetch_tickers()
                    books = {}
                    for pair_name in pairs:
                        pair = tickers.get(pair_name)
                        if pair:
                            pair["bids"] = [(pair["bid"], pair["quoteVolume"] or float("inf"))]
                            pair["asks"] = [(pair["ask"], pair["quoteVolume"] or float("inf"))]
                            books[pair_name] = pair
                break
            except (TimeoutError, RequestTimeout):
                logging.warning("Timeout while requesting tickers from {exchange.name}")

        logging.log(level=logging.DEBUG if marginal else logging.INFO,
                    msg=f"Loaded {len(books)} markets at {exchange}.")

        for pair, data in books.items():
            coin1, coin2 = pair.split("/", 1)
            try:
                if not coin1 or not coin2 or not data["bids"] or not data["asks"]:
                    continue
            except TypeError as e:
                # logging.warning(f"{e} when processing {pair}; data is {data}")
                continue

            if coin1 not in marginal:
                marginal[coin1] = {}

            if coin2 not in marginal:
                marginal[coin2] = {}

            # e.g. ETH/USD:
            # coin1 = ETH
            # coin2 = USD
            # The table is "from -> to", so "I have ETH and I want USD" means selling,
            # which means placing an order at the bid to get a fill.
            # Going the other way entails buying at 1 / the ask in USD.
            marginal[coin1][coin2] = [(bid, volume) for bid, volume in data["bids"]
                                      if bid and bid > 0]
            marginal[coin2][coin1] = [(1 / ask, ask * volume)
                                      for ask, volume in data["asks"] if ask and ask > 0]

    def get_pairs(self):
        """Returns all currency pairs in this table."""
        pairs = defaultdict(list)
        for exchange in self.values():
            for from_cur, marginal in exchange.items():
                for to_cur in marginal.keys():
                    pairs[from_cur].append(to_cur)
        return pairs

    def pairwise_diffs(self, from_cur, to_cur, snapshot=None) -> Tuple[Dict, Dict]:
        """Returns pairwise absolute and % differences between exchanges for a currency pair.

        Values represent profit from buying on the row, selling on the column."""
        snapshot = snapshot or self.copy()  # Prevent changes midway.
        absdiffs = {}
        pctdiffs = {}

        for exchange1 in snapshot.keys():
            for exchange2 in snapshot.keys():
                if absdiffs.get(exchange1, {}).get(exchange2, {}):
                    continue

                e1pair = RateTable._synget(snapshot, exchange1, from_cur, to_cur)
                e2pair = RateTable._synget(snapshot, exchange2, from_cur, to_cur)

                if not e1pair or not e2pair:
                    continue

                buyone = e2pair[0][0] - e1pair[0][0]

                if exchange1 not in absdiffs:
                    absdiffs[exchange1] = {}
                    pctdiffs[exchange1] = {}

                if exchange2 not in absdiffs:
                    absdiffs[exchange2] = {}
                    pctdiffs[exchange2] = {}

                absdiffs[exchange1][exchange2] = buyone
                pctdiffs[exchange1][exchange2] = buyone / e1pair

            if exchange1 in absdiffs:
                absdiffs[exchange1] = OrderedDict(
                    sorted(absdiffs[exchange1].items(),
                           key=lambda x: x[1] or float("-inf"), reverse=True))
                pctdiffs[exchange1] = OrderedDict(
                    sorted(pctdiffs[exchange1].items(),
                           key=lambda x: x[1] or float("-inf"), reverse=True))

        absdiffs = OrderedDict(sorted(absdiffs.items(),
                                      key=lambda x: nth(x[1].values(), 1, None) or float("-inf"),
                                      reverse=True))
        pctdiffs = OrderedDict(sorted(pctdiffs.items(),
                                      key=lambda x: nth(x[1].values(), 1, None) or float("-inf"),
                                      reverse=True))
        return absdiffs, pctdiffs

    @staticmethod
    def get_market_price(book, volume):
        """Returns the average market price, limit, and amount of new currency to fill an order."""
        total_price = 0
        remaining_volume = volume
        for order_price, order_vol in book:
            take = min(remaining_volume, order_vol)
            remaining_volume -= take
            total_price += take * order_price
            if remaining_volume <= 0:
                avg_price = total_price / volume
                return avg_price, order_price, volume * avg_price
        return None, None, None

    def best_roundtrips(self, cur, amount, exchanges=None, coins=None, max_steps=4):
        """Find the most profitable roundtrips from one currency to itself across exchanges.

        Returns a list of pairs to trade, sorted by overall profitability.
        Call profitability() on the result to get the profitability as a percentage.
        """

        conversions = self._all_conversions(cur, cur, amount, [], 0,
                                            max_steps, exchanges, coins, self.copy())
        return sorted(conversions, key=Trade.profitability, reverse=True)

    def _all_conversions(self, from_cur, to_cur, amount, trades, step, max_steps,
                         exchanges, coins, snapshot):
        syn_from = RateTable.SYNONYMS.get(from_cur)
        syn_to = RateTable.SYNONYMS.get(to_cur)
        if (from_cur == to_cur or from_cur == syn_to or syn_from == to_cur
                or (syn_from == syn_to and syn_from)) and trades:
            return [trades]

        if step >= max_steps:
            return []

        solutions = []
        for exchange_name, exchange in snapshot.items():
            if exchanges and exchange_name not in exchanges:
                continue

            direct_pairs = exchange.get(from_cur, {}).items()
            syn_pairs = exchange.get(RateTable.SYNONYMS.get(from_cur), {}).items()

            next_len = len(direct_pairs) + len(syn_pairs)
            logging.debug(f"On {exchange_name}, {next_len} {from_cur} pairs")

            no_volume = 0
            repeat_trades = 0
            for next_cur, book in itertools.chain(direct_pairs, syn_pairs):
                value, limit, next_amount = self.get_market_price(book, amount)

                if not value or (coins and next_cur not in coins):
                    no_volume += 1
                    continue

                next_trade = Trade(exchange_name, from_cur, next_cur, next_amount, limit, value)
                pair = next_trade.get_unique()
                inv_pair = next_trade.get_unique_inv()
                pairs = set(t.get_unique() for t in trades)
                if pair in pairs or inv_pair in pairs:
                    # Don't repeat the same trades in a single chain.
                    repeat_trades += 1
                    continue

                solutions += self._all_conversions(
                    next_cur, to_cur, next_amount,
                    trades + [next_trade],
                    step + 1, max_steps, exchanges, coins, snapshot)

            if step == 0:
                logging.debug(f"Trading {from_cur} on {exchange_name}, {no_volume} no-volume, "
                              f"{repeat_trades} repeats, {len(solutions)} solutions")

        return solutions

    @staticmethod
    def _synget(snapshot, exchange, from_cur, to_cur):
        if exchange not in snapshot:
            return None

        row = snapshot[exchange].get(from_cur) or snapshot[exchange].get(
            RateTable.SYNONYMS.get(from_cur))
        if not row:
            return None

        col = row.get(to_cur) or row.get(RateTable.SYNONYMS.get(to_cur))
        return col

    def __str__(self):
        super(RateTable, self).__str__()