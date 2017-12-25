import collections
from collections import OrderedDict, defaultdict
from typing import Dict, Tuple

from more_itertools import nth


class RateTable(collections.UserDict):
    SYNONYMS = {
        "XBT": "BTC",
        "BCC": "BCH",
        "USDT": "USD"
    }

    SYNONYMS.update({v: k for k, v in SYNONYMS.items()})

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

                buyone = e2pair - e1pair

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

    def best_conversions(self, from_cur, to_cur, max_steps=5):
        """Find conversion from one currency to another across exchanges, sorted by profitability.

        From_cur and to_cur can be the same currency - we'll look for profitable round trips.

        Returns a list of pairs to trade.
        """

        def profitability(chain):
            profit = 1.0
            for trade in chain:
                profit *= trade[-1]
            return profit

        conversions = self._all_conversions(from_cur, to_cur, [], 0, max_steps, self.copy())
        return sorted(conversions, key=profitability, reverse=True)

    def _all_conversions(self, from_cur, to_cur, trades, step, max_steps, snapshot):
        if step >= max_steps or (from_cur == to_cur and trades):
            return [trades]

        solutions = []
        for exchange_name, exchange in snapshot.items():
            for next_cur, value in exchange.get(from_cur, {}).items():
                if (exchange_name, from_cur, next_cur, value) in trades:
                    continue
                solutions += self._all_conversions(
                    next_cur, to_cur, trades + [(exchange_name, from_cur, next_cur, value)],
                    step + 1, max_steps, snapshot)
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
