# Disclaimer & Risk Notice

**Read this before using Krypt Trader with real money.**

Krypt Trader is free, open-source, experimental software for placing trades on
[Kalshi](https://kalshi.com). By downloading, building, or running it, you
acknowledge and accept everything below.

## Not financial advice
Krypt Trader, its strategies, signals, scores, and any documentation are for
informational and educational purposes only. Nothing here is financial,
investment, legal, or tax advice. The authors are **not** registered investment
advisors, commodity trading advisors, broker-dealers, or fiduciaries of any
kind, and nothing in this project creates such a relationship.

## Risk of loss
Trading event contracts involves substantial risk. **You can lose some or all
of the money in your account.** Automated trading can lose money quickly and at
scale, including while you are away from your computer. Only trade with money
you can afford to lose entirely.

## The strategies are unproven
The bundled strategies (whale tracker, momentum scanner, 15-minute crypto, etc.)
are **heuristics**. They:

- have **not** been validated with out-of-sample backtesting;
- do **not** currently account for Kalshi trading fees in their entry/sizing
  decisions, which can erode or eliminate any apparent edge;
- carry **no guarantee of profitability**.

Any performance figures, "edge" scores, or calibration claims are illustrative
and are **not** a promise of future results. Past or simulated performance does
not indicate future performance.

## No warranty
The software is provided "AS IS", without warranty of any kind, as stated in the
[LICENSE](./LICENSE). It may contain bugs that cause incorrect orders, missed
orders, or inaccurate P&L. The authors are not liable for any losses, damages,
or claims arising from its use.

## Your responsibilities
You are solely responsible for:

- Complying with [Kalshi's Terms of Service](https://kalshi.com/terms) and API
  terms, including any rules on automated/algorithmic trading. **Confirm that
  automated trading with your account is permitted before enabling it.**
- Complying with all laws and regulations in your jurisdiction, including
  eligibility, age, and licensing requirements.
- The security of your own Kalshi API keys and the machine you run this on.
- Every order the software places on your behalf.

## Use demo + dry-run first
Krypt Trader ships defaulted to Kalshi's **demo** environment with **dry-run**
enabled. Keep it that way until you fully understand the software and the risks.
Going live requires deliberately disabling both safeguards.

If you do not agree with any of the above, do not use this software.
