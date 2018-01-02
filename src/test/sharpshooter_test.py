import logging
import unittest

import more_itertools

from src.sharpshooter import Sharpshooter
from src.test.mock_exchange import MockExchange


class SharpshooterTest(unittest.TestCase):
    def setUp(self):
        super(SharpshooterTest, self).setUp()
        logging.basicConfig(level=logging.DEBUG)
        self.exchange = MockExchange()

    def test_finds_three_stage_arb(self):
        self.exchange.add_ask("BTC/USD", 10000, 20000)
        self.exchange.add_bid("BTC/USD", 10000, 20000)
        self.exchange.add_ask("ETH/BTC", 0.05, 1000)
        self.exchange.add_bid("ETH/BTC", 0.05, 1000)
        self.exchange.add_ask("ETH/USD", 750, 40)
        self.exchange.add_bid("ETH/USD", 750, 40)
        result = more_itertools.one(Sharpshooter([self.exchange], ("USD", 10000),
                                                 arbitrage_threshold_pcent=0.05).run_once())
        trade, profit = result
        self.assertEqual(0.5, profit)
        self.assertEqual("Mock Exchange", trade[0]["exchange"])
        self.assertEqual(["USD", "BTC", "ETH"], [t["from_cur"] for t in trade])
        self.assertEqual(["BTC", "ETH", "USD"], [t["next_cur"] for t in trade])
