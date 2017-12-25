import collections
from collections import OrderedDict
from typing import Dict, Tuple

from more_itertools import first, nth


class RateTable(collections.UserDict):
    SYNONYMS = {
        "XBT": "BTC",
        "BCC": "BCH",
        "USDT": "USD"
    }

    SYNONYMS.update({v: k for k, v in SYNONYMS.items()})

    def pairwiseDiffs(self, from_cur, to_cur) -> Tuple[Dict, Dict]:
        """Returns pairwise absolute and % differences between exchanges for a currency pair.

        Values represent profit from buying on the row, selling on the column."""
        snapshot = self.copy()  # Prevent changes midway.
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

                buyone = e2pair["bid"] - e1pair["ask"]

                if exchange1 not in absdiffs:
                    absdiffs[exchange1] = {}
                    pctdiffs[exchange1] = {}

                if exchange2 not in absdiffs:
                    absdiffs[exchange2] = {}
                    pctdiffs[exchange2] = {}

                absdiffs[exchange1][exchange2] = buyone
                pctdiffs[exchange1][exchange2] = buyone / e1pair["ask"]

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
    def _synget(snapshot, exchange, from_cur, to_cur):
        if exchange not in snapshot:
            return None

        row = snapshot[exchange].get(from_cur) or snapshot[exchange].get(
            RateTable.SYNONYMS.get(from_cur))
        if not row:
            return None

        col = row.get(to_cur) or row.get(RateTable.SYNONYMS.get(to_cur))
        return col
