# Sharpshooter
Multi-step cryptocurrency arbitrage bot using asyncio

I wrote this bot for personal use in the fall of 2017. It's unique in that it can compute arbitrage opportunities which involve multiple crypto transactions.

There are many more coins now (April 2018), performance has slowed with the increase, and arbitrage is less profitable than it once was, so I'm opensourcing Sharpshooter under the GPL v3, having extracted what value I could from it while cryptocurrency was hot.

If you'd like to use this code in a closed-source product, contact me for an alternative commercial license.

## To run:

```python3 sharpshooter.py```

This codebase liberally uses async/await, so you'll need at least Python 3.5 to run it.

By default, the code assumes you're starting with 10 ETH. This can be changed at the bottom of sharpshooter.py.
