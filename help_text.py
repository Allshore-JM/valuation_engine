"""Plain-English explanations shown in the Streamlit UI (help bubbles + expanders).

Kept separate from the app layout so the copy is easy to read and edit. Strings are
markdown — they render in Streamlit `help=` tooltips and `st.markdown(...)` blocks.
"""

# ----------------------------------------------------------------- big intro (expander)
INTRO = """\
### What this tool does

It estimates what a company is **worth** — its *intrinsic value* — and compares that to
what the stock actually **costs** today. A large gap is a prompt to dig into *why*, not an
automatic buy/sell signal.

It answers the question two independent ways:

**1 · Discounted cash flow (DCF) — "what are the future profits worth today?"**
A business is worth all the cash it will hand its owners over its life. But a dollar ten
years from now is worth less than a dollar today — you could invest today's dollar, and the
future is uncertain — so every future dollar is **discounted** back to today and added up.
That sum is the intrinsic value. We compute it three ways (FCFF, FCFE, DDM — see the
*Summary* tab), and they should roughly agree.

**2 · Relative valuation — "what do similar companies cost?"**
If comparable companies trade at, say, 20× earnings and ours is similar, it "should" too —
after adjusting for differences in growth and profitability. We compare the target against a
group of peers to predict a *fair* price multiple for it.

### How to use it
1. Pick a company (and a few peers) in the sidebar.
2. Every assumption starts at a sensible value estimated from the company's **own history** —
   move the sliders to reflect *your* view and watch the valuation change live.
3. The **Sensitivity** tab shows which assumption matters most, **Monte Carlo** shows the
   range of outcomes, and **Full report** gives a downloadable, auditable write-up.

> **Not investment advice.** These are model estimates, only as good as the assumptions —
> *garbage in, garbage out.* The real value is seeing how the answer moves as you change
> your view, and understanding *why*.
"""

# --------------------------------------------------------------------------- inputs
DATA_SOURCE = (
    "**Offline** replays bundled example data (Apple, Coca-Cola and their peers) instantly — "
    "perfect for trying the tool with no network. **Live** pulls any ticker's latest "
    "financials from Yahoo Finance (slower, and occasionally rate-limited)."
)

TICKER = (
    "The stock symbol to value — e.g. `AAPL` (Apple), `MSFT` (Microsoft), `KO` (Coca-Cola). "
    "In Live mode you can enter any publicly listed company."
)

PEERS = (
    "A handful of **similar companies** in the same industry. The relative valuation asks: "
    "given how these peers are priced, what is the target worth? Pick genuinely comparable "
    "firms — comparing a software maker to an oil producer won't tell you much."
)

WACC = """\
**Weighted Average Cost of Capital** — the blended yearly return the company must earn to
keep *all* its funders (shareholders **and** lenders) satisfied.

It is the **discount rate** for the whole firm: cash the company earns years from now is
worth less than cash today, and WACC sets how much less.

*Built as:* (cost of equity × % equity) + (after-tax cost of debt × % debt), at market values.

*Rule of thumb:* ~6–12% for established firms. **Lowering it raises the valuation** — and it
is usually the single most powerful input, which is why the Sensitivity tab almost always
ranks it first.
"""

KE = """\
**Cost of equity** — the yearly return *shareholders* demand for the risk of owning this
stock. It discounts the cash flows that belong to shareholders (FCFE and dividends).

*Built as (CAPM):* risk-free rate + beta × equity-risk-premium — a more volatile stock
(higher beta) requires a higher return. *Typical:* ~7–12%.
"""

HIGH_GROWTH = """\
How fast you expect the company's **operating profit to grow** over the first five years (the
"high-growth phase").

Growth is **not free**: a company grows by *reinvesting* — new equipment, acquisitions,
working capital — and earning a return on it. So growth ≈ *reinvestment rate × return on
capital*. The suggested value is backed out from the firm's own recent reinvestment and
returns.

Be skeptical of large numbers — very few companies sustain >15–20% growth for long.
"""

STABLE_GROWTH = """\
After the high-growth years, the company is assumed to grow **forever** at this steady rate.
This single number drives the **terminal value**, which is often the *majority* of the total —
so handle it with care.

**Capped at the risk-free rate.** A company can't outgrow the whole economy forever (it would
eventually become larger than the economy), and the long-term government-bond yield is our
stand-in for long-run economic growth. *Typical:* 2–3%.
"""

TAX = (
    "The **marginal tax rate** applied to operating profit. Cash flows are valued *after tax*, "
    "because that is what is actually left for investors. The suggestion is the firm's recent "
    "effective rate; the US federal statutory rate is 21%."
)

STABLE_ROC = """\
In the forever-phase, the **return the company earns on each dollar it reinvests**.

Setting it **equal to WACC** means the firm earns exactly its cost of capital — no *excess*
return — a conservative, common default for a mature business. Set it higher only if you
believe in a durable competitive advantage (a "moat") that lets the firm keep earning
above-average returns.
"""

RF = (
    "**Risk-free rate** — the yield on a long-term government bond, i.e. the return you can earn "
    "with virtually no risk. It anchors every other rate in the model and caps long-run growth."
)

ERP = (
    "**Equity risk premium** — the *extra* annual return investors demand for holding stocks "
    "instead of safe bonds (historically ~4–5%). Higher premium → higher cost of equity → "
    "lower value."
)

BETA = (
    "**Beta** measures how much the stock swings relative to the overall market. 1.0 = moves "
    "with the market; above 1 = more volatile (riskier, higher required return); below 1 = steadier."
)

MC_ITER = (
    "How many random scenarios to simulate. The tool re-runs the valuation this many times — "
    "each with the assumptions nudged randomly around your inputs — to produce a **range** of "
    "values and the probability the stock is undervalued."
)

# --------------------------------------------------------------------------- outputs
M_PRICE = "What one share trades for right now. Every estimate below is compared against this."

M_INTRINSIC = (
    "The middle estimate from the **discounted-cash-flow** methods (FCFF, FCFE, DDM) — what the "
    "business is worth based on the cash it can generate, regardless of today's market mood."
)

M_RELATIVE = (
    "The middle estimate from **peer multiples** — what the stock would be worth if priced like "
    "comparable companies, adjusted for its growth and profitability."
)

M_MOS = """\
**Margin of safety** = (intrinsic value − price) ÷ intrinsic value.

**Positive** → the stock trades *below* your estimate of value (a cushion if your assumptions
are too optimistic). **Negative** → it trades *above* your estimate. Value investors look for a
comfortable positive margin before buying.
"""

METHODS = """\
**FCFF — Free Cash Flow to the Firm.** Values the *entire business* from its after-tax
operating cash flows, discounts them at **WACC**, then subtracts net debt to reach equity
value per share. The best general-purpose method.

**FCFE — Free Cash Flow to Equity.** Values only the cash left for *shareholders* after
lenders are paid, discounted at the **cost of equity**. A cross-check on FCFF — for a
lightly-indebted firm the two should land close together.

**DDM — Dividend Discount Model.** Values only the **dividends** the company actually pays
out, discounted at the cost of equity. Best for steady dividend payers, and usually a *floor*
because it ignores cash the company keeps and reinvests. (Apple pays a small dividend, so its
DDM figure sits far below its FCFE.)

**relative · P/E · P/B · EV/EBITDA · EV/Sales.** What the stock is worth if it traded at the
*fair* multiple for its peer group — where "fair" is predicted from the peers' growth and
profitability, not a blind average.

On the chart, the **red dashed line is the current market price**: bars to its right suggest
that method sees upside; bars to its left suggest the stock looks expensive.
"""

UPSIDE = (
    "(estimate − price) ÷ price — how far the stock would have to move to reach this estimate. "
    "+20% means the estimate is 20% above today's price."
)

REVERSE_DCF = (
    "Works **backwards**: what high-growth rate would justify the *current price*? If that "
    "'implied' growth is far above anything the company has ever achieved, the market is pricing "
    "in heavy optimism; if it's low, the market is cautious. A reality check on the price — not a verdict."
)

SENSITIVITY = (
    "Which assumption matters most? Each bar moves **one** input up and down and measures how far "
    "the value swings. The longest bar is what your answer hinges on (usually WACC) — that's where "
    "to focus your research."
)

SCENARIOS = (
    "Three coherent stories: **Bull** (cheaper capital + faster growth), **Base** (your current "
    "sliders), and **Bear** (the reverse). A fast read on the plausible range of value."
)

MONTE_CARLO = (
    "Randomizes the key assumptions thousands of times and plots the resulting values. The "
    "**spread** shows how uncertain the estimate is; **P(value > price)** is the share of "
    "simulations in which the stock looks undervalued. The red line is today's price."
)

# --------------------------------------------------------------------------- glossary
GLOSSARY = """\
- **Intrinsic value** — what a business is worth based on the cash it generates, independent of its market price.
- **Discount rate** — the annual % used to shrink future cash to today's value (WACC for the firm, cost of equity for shareholders). Higher rate → lower value.
- **FCFF / FCFE** — free cash flow to the firm / to equity: the cash a business / its shareholders actually get to keep after running and growing the business.
- **WACC** — weighted average cost of capital: the blended required return of lenders and shareholders.
- **Cost of equity** — shareholders' required return (CAPM = risk-free rate + beta × equity-risk-premium).
- **Beta** — how much the stock moves relative to the market (1.0 = the same).
- **Risk-free rate** — long-term government-bond yield: a near-zero-risk return, and the cap on long-run growth.
- **Equity risk premium (ERP)** — the extra return demanded for holding stocks over bonds.
- **Terminal value** — the value of all cash flows *beyond* the explicit forecast (the "forever" phase); often most of the total.
- **Reinvestment rate** — the share of profit ploughed back in to fund growth.
- **Return on capital (ROC)** — profit earned per dollar of capital invested.
- **Multiple** — a price ratio such as P/E (price ÷ earnings) used to compare companies.
- **Terminal value warning** — flagged when the "forever" phase makes up most of the value, meaning the answer rests heavily on far-future guesses.
- **Margin of safety** — how far the price sits below your estimate of value.
"""
