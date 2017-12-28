from collections import UserDict


class Trade(UserDict):
    def __init__(self, exchange, from_cur, next_cur, amount, limit, value):
        super(Trade, self).__init__(
            exchange=exchange,
            from_cur=from_cur,
            next_cur=next_cur,
            amount=amount,
            limit=limit,
            value=value
        )

    @staticmethod
    def profitability(trades):
        """Returns the profitability as a percentage of a given chain."""
        profit = 1.0
        for trade in trades or []:
            profit *= trade["value"]
        return profit - 1.0

    @staticmethod
    def num_exchanges(trades):
        """Returns the number of exchanges coins traverse in this chain."""
        exchanges = set()
        for trade in trades:
            exchanges.add(trade["exchange"])
        return len(exchanges)
