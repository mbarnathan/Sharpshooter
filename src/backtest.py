#!/usr/bin/python

import sys
import csv
import pydash
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

starting_funds = 10000

funds = starting_funds
cb = []

ohlc = csv.reader(sys.stdin)
ticks = pydash.arrays.unzip(ohlc)
timestamps = np.asarray(list(map(int, ticks[0])))
opens, highs, lows, closes = (np.asarray(list(map(float, e))) for e in ticks[1:5])

sma = pd.Series(opens).rolling(10).mean()

for tick in range(len(timestamps)):
  price = opens[tick]
  if sma[tick] >= price and funds > 0 and not cb:
    # Buy
    qty = funds / price
    funds = 0
    print(f"{timestamps[tick]}: Bought {qty} BTC at ${price:.2f}, funds = ${funds:.2f}")
    cb.append((timestamps[tick], qty, price))
  elif cb and highs[tick] > cb[0][2] + 100 / cb[0][1]:
    # Sell
    bought, qty, cost_basis = cb.pop()
    profit = qty * (highs[tick] - cost_basis)
    funds += qty * highs[tick]
    held = int((timestamps[tick] - bought) / 60)
    print(f"+{held}m: Sold {qty} BTC at ${highs[tick]:.2f}, cb = ${cost_basis:.2f}, profit = ${profit:.2f}, funds = ${funds:.2f}")
  
for _, qty, _ in cb:
  funds += qty * closes[-1]

print(f"Ended with {funds:.2f}")
print(f"Holding would have ended with {starting_funds / opens[0] * closes[-1]:.2f}")

#plt.plot(opens)
#plt.plot(sma)
#plt.show()
