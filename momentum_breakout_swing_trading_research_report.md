# Momentum Breakout Swing-Trading Systems

**Evidence Review, Strategy Assessment, and Backtesting Blueprint**

**Prepared for:** Ramon Carmenaty  
**Date:** 13 July 2026  
**Purpose:** Research only

> This report evaluates published evidence and converts it into testable system specifications. It is not personalized investment advice, a promise of profitability, or a recommendation to deploy capital without independent validation.

---

# 1. Executive summary

> **Bottom line**
>
> The most defensible swing-trading design is a long-only, liquid-equity system that selects established intermediate-term winners, requires price to remain close to its 52-week high, enters only on an objective trading-range breakout, and scales portfolio risk down when volatility rises. The breakout is the timing mechanism; momentum and the 52-week-high condition supply the stronger empirical foundation.

This report reviews the principal findings from academic work on cross-sectional momentum, time-series momentum, the 52-week-high effect, volume, momentum crashes, volatility management, trend following, post-earnings-announcement drift, and the methodological weaknesses common in technical-strategy research. It then translates those findings into three testable swing-trading systems and ranks them by evidentiary strength, practicality, and robustness.

## Principal conclusions

**Momentum is a selection effect before it is an entry signal.** The evidence is strongest for persistence among assets or stocks that have already outperformed over intermediate horizons. A short-term breakout can improve timing, but a breakout by itself is not equivalent to academic momentum.

**The 52-week high is the most relevant bridge between the literature and breakout trading.** Stocks trading close to their major high contain more information than a generic moving-average crossover or arbitrary chart pattern. This makes proximity to the 52-week high a high-priority filter.

**Risk control materially changes the quality of a momentum system.** Momentum returns can be negatively skewed and vulnerable during sharp rebounds after broad market declines. Volatility scaling, exposure caps, and regime filters should be part of the core design rather than added after signal optimization.

**Volume is useful, but simplistic volume rules are not well justified.** The literature supports interaction between past turnover and momentum persistence, but it does not validate the universal rule that every breakout must occur on two times average volume. Volume should be tested as a continuous context variable rather than treated as dogma.

**Earnings continuation is plausible but less dependable as a modern large-cap edge.** Post-earnings drift is historically well documented, yet more recent work argues that much of it has weakened in highly liquid stocks. An earnings-breakout strategy should therefore be treated as a secondary, event-driven hypothesis.

**Visual contraction patterns are the least evidence-backed element.** Volatility contraction can be encoded objectively and may help reduce false breakouts, but discretionary pattern labels such as “VCP” are not supported by evidence comparable to the momentum and 52-week-high literature.

## Recommended research priority

**1.** Backtest the Core 52-Week-High Momentum Breakout first.

**2.** Compare it against a plain 20-day breakout to measure the incremental value of momentum and high-proximity filters.

**3.** Add volatility contraction only after the core system survives out-of-sample testing.

**4.** Treat the earnings-gap continuation model as a separate event strategy, not as an extra condition added to every trade.

| **Rank**  | **Strategy**                                | **Evidence**                   | **Expected role**      | **Assessment**                                          |
|-----------|---------------------------------------------|--------------------------------|------------------------|---------------------------------------------------------|
| 1         | Core 52-Week-High Momentum Breakout         | High                           | Primary research model | Best synthesis of the reviewed literature               |
| 2         | Momentum + Objective Volatility Contraction | Medium                         | Precision variant      | Promising, but more parameter-sensitive                 |
| 3         | Post-Earnings Gap Continuation              | Medium-low                     | Event-driven satellite | Potential edge; likely less stable in liquid large caps |
| Benchmark | Plain N-Day Breakout                        | Low as a stock-selection model | Control strategy       | Essential comparison, not preferred final design        |

# 2. Contents and scope

1. [Executive summary](#1-executive-summary)
2. [Contents and scope](#2-contents-and-scope)
3. [What the literature actually supports](#3-what-the-literature-actually-supports)
4. [Evidence assessment by study](#4-evidence-assessment-by-study)
5. [From academic momentum to swing-trading rules](#5-from-academic-momentum-to-swing-trading-rules)
6. [Recommended strategy: Core 52-Week-High Momentum Breakout](#6-recommended-strategy-core-52-week-high-momentum-breakout)
7. [Alternative strategy: Momentum with volatility contraction](#7-alternative-strategy-momentum-with-volatility-contraction)
8. [Alternative strategy: Post-earnings gap continuation](#8-alternative-strategy-post-earnings-gap-continuation)
9. [Risk management and portfolio construction](#9-risk-management-and-portfolio-construction)
10. [Backtesting and validation protocol](#10-backtesting-and-validation-protocol)
11. [Failure modes and common mistakes](#11-failure-modes-and-common-mistakes)
12. [Implementation roadmap](#12-implementation-roadmap)
13. [References](#13-references)

## Scope

The review focuses on daily-data systems suitable for holding periods from several days to roughly three months. The primary use case is a systematic or semi-systematic long-only equity strategy, although several principles generalize to diversified futures and other liquid markets. The report does not claim that the exact proposed thresholds are established by the papers; thresholds are research starting points selected to operationalize the findings.

> **Important distinction**
>
> Academic momentum usually refers to portfolio formation based on ranked prior returns over months. “Breakout trading” usually refers to entry after price exceeds a recent high. The recommended system deliberately combines the two: momentum selects candidates; the breakout controls timing and defines invalidation.

# 3. What the literature actually supports

## 3.1 Cross-sectional momentum

The foundational equity evidence shows that buying prior winners and selling prior losers over intermediate horizons historically generated return continuation. For a long-only swing system, the direct implication is to concentrate entries among the strongest stocks in the tradable universe rather than taking every chart breakout. [1]

- Operational implication: rank stocks by prior six- or twelve-month return, normally excluding the most recent few weeks to reduce short-term reversal contamination.

- System implication: use relative momentum as a candidate-selection layer, not merely as a confirmation indicator after a breakout occurs.

- Limitation: the classic research often studies long-short portfolios, broad universes, and monthly rebalancing; it does not directly prove that a particular daily breakout entry is profitable.

## 3.2 The 52-week-high effect

Research on the 52-week high finds that nearness to the prior annual high explains a meaningful portion of momentum profitability and can improve on forecasts based on prior returns alone. This is the single most relevant finding for a breakout-oriented stock system because it links a psychologically salient reference point to subsequent continuation. [2]

- Operational implication: prefer candidates within approximately 0-10% of their 52-week high, with tighter bands tested separately.

- Interpretation: a stock near its annual high is not automatically a buy; it becomes a high-quality candidate when combined with relative strength, liquidity, and an objective entry trigger.

- Limitation: the paper tests portfolio sorts, not the exact 20-day breakout and stop rules proposed in this report.

## 3.3 Time-series momentum and absolute trend

Time-series momentum research documents persistence in an asset’s own returns over approximately one to twelve months across multiple liquid asset classes. For an equity swing system, this supports requiring both the individual stock and the broader market to be in positive trends before initiating long exposure. [3]

- Operational implication: add an absolute trend requirement, such as price above a rising long-term moving average.

- Portfolio implication: reduce or suspend new long entries when the benchmark index is below its long-term trend filter.

- Limitation: much of the strongest diversified time-series evidence comes from futures, not from long-only single-stock swing trades.

## 3.4 Trading volume

The volume literature indicates that past turnover contains information about the magnitude and persistence of momentum and may help distinguish earlier-stage from later-stage momentum. It does not establish a universal breakout-volume multiplier. [4]

- Operational implication: test turnover percentile, recent volume trend, and breakout-day dollar volume separately.

- Avoid: defining “valid breakout” as volume above an arbitrary multiple without measuring whether the rule adds out-of-sample value.

- Practical compromise: require sufficient liquidity, then use volume as a ranking feature or soft score rather than an absolute veto.

## 3.5 Momentum crashes and volatility management

Momentum strategies have historically displayed negative skew and episodic crashes, particularly after market declines, during elevated volatility, and alongside sharp market rebounds. Separate research finds that volatility-managed momentum materially improved risk-adjusted performance in historical samples. [5][6]

- Operational implication: risk per position should fall when stock or portfolio volatility rises.

- Regime implication: avoid maximum gross exposure immediately after severe market declines when volatility remains high and the market begins a violent rebound.

- Design implication: maximum drawdown control should be tested at the portfolio level, not left to independent stop-losses alone.

## 3.6 Long-run trend-following evidence

The long historical record for diversified trend following supports the proposition that price trends are persistent across markets and macroeconomic regimes. It strengthens the case for rule-based exits that allow winners to run, but it should not be interpreted as proof that a concentrated equity breakout portfolio will inherit the same crisis behavior. [7]

## 3.7 Technical-analysis research quality

Reviews of technical-analysis studies warn that apparent profitability is often weakened by data snooping, optimized parameters, incomplete transaction-cost assumptions, and inadequate out-of-sample verification. These warnings are central to the research design recommended later in this report. [8]

## 3.8 Post-earnings-announcement drift

Post-earnings drift is a historically documented continuation effect after earnings surprises. However, recent evidence suggests that the anomaly has weakened or disappeared for many large, liquid stocks. Earnings-related continuation remains testable, but it should not receive the same confidence rating as general momentum or the 52-week-high effect. [9][10]

# 4. Evidence assessment by study

| **Study**                        | **Primary subject**            | **Main finding**                                                           | **Confidence**    | **System-design implication**                                              |
|----------------------------------|--------------------------------|----------------------------------------------------------------------------|-------------------|----------------------------------------------------------------------------|
| Jegadeesh & Titman (1993)        | Prior winners versus losers    | Strong support for intermediate-term cross-sectional momentum              | High              | Use ranked prior returns to select candidates; not an entry rule by itself |
| George & Hwang (2004)            | Price relative to 52-week high | Nearness to the annual high improves momentum forecasting                  | High              | Make high-proximity a core filter                                          |
| Moskowitz, Ooi & Pedersen (2012) | Own past return across futures | Return persistence over 1-12 months across asset classes                   | High              | Use absolute-trend and market-regime filters                               |
| Lee & Swaminathan (2000)         | Price momentum and turnover    | Volume predicts momentum magnitude and persistence                         | Medium-high       | Use volume context, not a simplistic breakout multiplier                   |
| Daniel & Moskowitz (2016)        | Momentum crash states          | Crashes cluster in panic/rebound states                                    | High              | Reduce exposure during high-volatility rebounds                            |
| Barroso & Santa-Clara (2015)     | Volatility-managed momentum    | Risk varies predictably; scaling improved historical risk-adjusted returns | High              | Volatility-target positions and portfolio                                  |
| Hurst, Ooi & Pedersen (2017)     | Trend following since 1880     | Positive average returns across decades and diverse regimes                | Medium-high       | Favor trailing exits and diversification                                   |
| Park & Irwin (2007)              | Review of technical rules      | Many findings vulnerable to methodology and costs                          | High as a warning | Require rigorous out-of-sample validation                                  |
| Fink (2021) / Martineau (2021)   | PEAD persistence               | Historical anomaly; modern large-cap edge may be attenuated                | Medium-low        | Keep earnings system separate and revalidate frequently                    |

## Assessment scale

“High” means the finding is central, widely influential, and directly relevant to system architecture, not that every implementation is guaranteed to work. “Medium” means the finding is useful but sensitive to market, sample, or translation into trading rules. “Low” would indicate that the proposition is primarily practitioner convention or a pattern hypothesis rather than a robust academic result.

# 5. From academic momentum to swing-trading rules

## 5.1 The layered architecture

| **Layer**              | **Question answered**                                 | **Preferred evidence-based rule**                                            | **What it prevents**                                        |
|------------------------|-------------------------------------------------------|------------------------------------------------------------------------------|-------------------------------------------------------------|
| Universe               | Can the position be entered and exited realistically? | Minimum price, market capitalization, and median dollar volume               | Microcap bias, unrealistic fills, excessive spread costs    |
| Relative momentum      | Is this stock a proven winner versus alternatives?    | Top 10-20% by 6- or 12-month return                                          | Buying visually attractive but weak stocks                  |
| 52-week-high proximity | Is the winner near a salient major high?              | Close within 5-10% of annual high                                            | Late entries after deep pullbacks or damaged trends         |
| Absolute trend         | Is the stock and market trend positive?               | Price above rising 50- and 200-day averages; benchmark above 200-day average | Long entries in broad downtrends                            |
| Setup quality          | Is price compressing or forming an orderly range?     | Optional objective contraction and range tests                               | Chasing extended price bars                                 |
| Trigger                | When is the thesis activated?                         | Close above prior 20- or 40-day high                                         | Subjective entries and anticipation                         |
| Position size          | How much loss is acceptable?                          | ATR/stop-distance sizing with volatility cap                                 | Inconsistent risk across securities                         |
| Exit                   | When is continuation no longer intact?                | Trailing low, moving average, or ATR stop                                    | Turning a trend strategy into hope or fixed-target scalping |

## 5.2 Why the breakout should remain simple

The entry trigger should be objective and parsimonious because the strongest edge is expected to come from candidate selection and risk management. A complex trigger with multiple candles, pattern labels, and volume exceptions increases the probability of overfitting. The base research model should therefore use a close above a prior N-day high, with the current day excluded from the lookback.

## 5.3 Why fixed profit targets are not preferred

Momentum and trend-following systems depend on a minority of outsized winners compensating for many small losses and failed breakouts. Fixed targets can truncate that positive tail. A trailing exit or channel exit is more aligned with the underlying return process, although it may produce lower win rates and more giveback from peak unrealized profit.

## 5.4 Why one universal stop is not preferred

A fixed percentage stop produces very different economic risk across stocks. A 5% move may be ordinary noise for a volatile growth stock and an extreme event for a defensive stock. Position sizing should normalize risk using stop distance and, ideally, current volatility. The stop rule should still be simple enough to audit and execute.

# 6. Recommended strategy: Core 52-Week-High Momentum Breakout

> **Assessment**
>
> This is the highest-priority system because it combines the strongest reviewed findings while keeping the entry rule simple. It is a research specification, not a claim that the selected thresholds are optimal.

## 6.1 Objective

Capture multi-week continuation in liquid stocks that are already demonstrating superior intermediate-term performance and are pressing toward major highs, while avoiding broad market downtrends and normalizing risk across positions.

## 6.2 Baseline rules

| **Component**          | **Baseline specification**                                                                                                                                                         | **Parameters to test**                                                   |
|------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Universe               | Primary-listed common stocks; price \>= 10; median 20-day dollar volume \>= 10 million; exclude ETFs, funds, preferred shares, warrants, and recent IPOs with insufficient history | Price 5/10/20; dollar volume 5/10/25 million; IPO seasoning 126/252 days |
| Relative momentum      | Rank by return from 252 trading days ago to 21 trading days ago; trade top 15%                                                                                                     | 6-1, 9-1, and 12-1 month returns; top 10/15/20%                          |
| 52-week-high proximity | Close \>= 95% of trailing 252-day high                                                                                                                                             | 90%, 93%, 95%, 97%, and new-high-only variants                           |
| Stock trend            | Close \> 50-day SMA \> 200-day SMA; 200-day SMA rising over prior 20 days                                                                                                          | EMA versus SMA; slope windows 10/20/40 days                              |
| Market regime          | Benchmark close above 200-day SMA; optional 50-day SMA above 200-day SMA                                                                                                           | No filter; 100-day; 200-day; dual-average                                |
| Entry                  | Buy next session after daily close exceeds prior 20-day high                                                                                                                       | 10/20/40/55-day highs; close versus stop entry                           |
| Initial stop           | Lower of breakout-day low or entry minus 2 ATR(20), subject to maximum stop-distance cap                                                                                           | 1.5/2/2.5/3 ATR; structural versus ATR                                   |
| Position risk          | 0.35% of equity per initial stop; lower when portfolio volatility is elevated                                                                                                      | 0.20%-0.75%; volatility targeting                                        |
| Exit                   | Close below prior 10-day low; execute next session                                                                                                                                 | 5/10/20-day low; 20-day EMA; 3 ATR trailing stop                         |
| Time stop              | Exit after 20 sessions if trade has not achieved at least +0.5R or closed at a new 20-day high                                                                                     | 10/20/30 days; remove time stop                                          |
| Portfolio cap          | Maximum 10 positions and 4% total open initial risk; sector exposure cap                                                                                                           | 6/10/15 positions; risk and correlation caps                             |

## 6.3 Signal sequence

**1.** At the end of each trading day, update the eligible universe using point-in-time security classifications and liquidity data.

**2.** Calculate relative momentum and retain only the highest-ranked segment.

**3.** Apply 52-week-high proximity and stock-trend filters.

**4.** Apply the benchmark market-regime filter.

**5.** Identify closes above the previous N-day high.

**6.** Rank simultaneous signals by momentum rank, high proximity, liquidity, and optional setup quality.

**7.** Size positions from the planned stop distance and current equity.

**8.** Execute using realistic next-session assumptions and track slippage separately.

**9.** Update trailing exits daily without loosening a stop after entry.

## 6.4 Why each rule is present

| **Rule**                     | **Research rationale**                                                    | **Expected cost**                                    |
|------------------------------|---------------------------------------------------------------------------|------------------------------------------------------|
| Top momentum rank            | Aligns trades with cross-sectional winner continuation                    | Higher turnover and crowding risk                    |
| Near 52-week high            | Uses a reference point shown to improve momentum forecasting              | May enter after substantial prior appreciation       |
| Market trend filter          | Uses own-market trend evidence and reduces long exposure in bear regimes  | Can re-enter late after fast reversals               |
| N-day breakout               | Provides an auditable activation point and avoids anticipating resistance | Whipsaws in range-bound markets                      |
| Volatility-normalized sizing | Addresses time-varying risk and crash exposure                            | Smaller positions after volatility has already risen |
| Trailing exit                | Preserves access to the right tail of winner returns                      | Gives back part of open profit                       |

## 6.5 Expected behavioral profile

- Win rate may be below 50%; profitability should come from average win exceeding average loss.

- Trade frequency should decline during weak markets because the market filter and candidate requirements remove signals.

- Returns may cluster in sustained bull trends and deteriorate in choppy, high-correlation reversals.

- The system will often buy stocks that appear “expensive” or extended on conventional valuation measures; this is intrinsic to momentum selection.

# 7. Alternative strategy: Momentum with volatility contraction

> **Assessment**
>
> This variant is plausible and may reduce low-quality breakouts, but it carries greater model-risk because “contraction” can be defined in many ways. It should only be added after the core model is established.

## 7.1 Objective definition of contraction

Replace visual pattern recognition with measurable conditions. A candidate can qualify when its recent realized volatility and trading range contract relative to earlier windows while price remains near the annual high.

| **Feature**                     | **Example objective definition**                                                  | **Reason for testing**                       |
|---------------------------------|-----------------------------------------------------------------------------------|----------------------------------------------|
| Range contraction               | Median true range over last 5 days \< 70% of median true range over prior 20 days | Measures quieter price movement              |
| Realized-volatility contraction | 10-day annualized volatility \< 20-day volatility \< 60-day volatility            | Tests progressive compression                |
| Tight close dispersion          | (Highest close - lowest close) over 5 days \<= 1.5 ATR(20)                        | Avoids wide, unstable bases                  |
| Orderly pullback                | Maximum drawdown from 20-day high \<= 1.5 ATR and close remains above 20-day EMA  | Filters damaged setups                       |
| Volume contraction              | Median 5-day volume \< median 20-day volume                                       | Tests reduced participation before expansion |
| Trigger                         | Close above consolidation high and prior 20-day high                              | Requires actual expansion before entry       |

## 7.2 Recommended research method

Do not require all contraction features simultaneously in the first test. Begin with the core model, add one feature at a time, and measure its incremental effect on expectancy, drawdown, turnover, trade count, and stability across subperiods. A feature that improves in-sample Sharpe by eliminating most trades but fails in the next period is not a robust improvement.

## 7.3 Evidence rating

The underlying concepts-volatility clustering, trend persistence, and avoiding unstable entries-are reasonable. However, the specific “volatility contraction pattern” is mainly a practitioner framework. It should receive a medium or lower evidence rating until objective definitions survive independent and out-of-sample tests.

# 8. Alternative strategy: Post-earnings gap continuation

> **Assessment**
>
> An earnings catalyst can supply new information and produce continuation, but modern evidence is mixed. Use this as a separate event strategy with its own data, execution model, and decay monitoring.

## 8.1 Baseline hypothesis

A large positive earnings-related gap accompanied by strong dollar volume and a close near the session high identifies a favorable information shock. A later breakout above the earnings-day high or a short post-event consolidation may capture residual underreaction.

## 8.2 Baseline rules

| **Component**     | **Baseline specification**                                          | **Research note**                                         |
|-------------------|---------------------------------------------------------------------|-----------------------------------------------------------|
| Universe          | Liquid stocks with reliable earnings timestamps and adjusted prices | Timestamp quality is essential to avoid event-date errors |
| Event             | Confirmed quarterly earnings release outside regular market hours   | Separate pre-open and after-close events                  |
| Gap               | Open at least +4% above prior close and above 1.5 ATR               | Test percentile-based gaps by stock volatility            |
| Event-day quality | Close in top 25% of daily range; dollar volume \>= 2x 20-day median | Captures sustained reaction, not only opening gap         |
| Trend context     | Positive 6-month relative momentum and above 200-day average        | Avoids fighting an established downtrend                  |
| Entry A           | Next-day break above earnings-day high                              | Fast continuation variant                                 |
| Entry B           | Break above 2-10 day post-gap consolidation                         | Lower-frequency delayed variant                           |
| Stop              | Below earnings-day midpoint or low, normalized by ATR               | Gap failures can reverse sharply                          |
| Exit              | 10-day low, 20-day EMA, or 20-40 session maximum hold               | PEAD horizon may extend, but implementation costs matter  |

## 8.3 Why it should not be merged blindly with the core system

Earnings trades have discontinuous overnight risk, event-specific data requirements, and different price formation. Combining them with ordinary breakouts can obscure whether performance comes from momentum, gap behavior, or event timing. Maintain separate attribution and risk budgets even if both systems eventually trade the same portfolio.

# 9. Risk management and portfolio construction

## 9.1 Position sizing

The preferred sizing model converts a fixed fraction of portfolio equity into shares based on the distance between intended entry and initial stop. For example, with portfolio equity E, risk fraction r, entry P, and stop S, the preliminary share quantity is floor((E x r) / (P - S)). The result must then be constrained by liquidity, maximum position value, and portfolio exposure limits.

> **Risk principle**
>
> A stop does not guarantee the planned loss. Overnight gaps, trading halts, and liquidity shocks can produce losses materially larger than the stop-distance calculation. Position risk must therefore be conservative enough to survive discontinuous moves.

## 9.2 Volatility scaling

Volatility can be incorporated at two levels: position sizing and portfolio exposure. Position-level ATR sizing prevents a volatile stock from receiving the same share count as a stable stock. Portfolio-level scaling reduces aggregate risk when realized portfolio or benchmark volatility rises. The latter is especially relevant to the crash evidence reviewed above.

## 9.3 Market-state controls

| **State**                 | **Observable condition**                                           | **Suggested response**                                    |
|---------------------------|--------------------------------------------------------------------|-----------------------------------------------------------|
| Normal uptrend            | Benchmark above 200-day average; moderate realized volatility      | Allow normal risk budget                                  |
| Weakening trend           | Benchmark below 50-day average but above 200-day average           | Reduce new-position risk or require higher-ranked setups  |
| Bear regime               | Benchmark below falling 200-day average                            | Suspend or sharply reduce long-only breakout entries      |
| Panic/rebound risk        | Large prior market decline, elevated volatility, and rapid rebound | Use reduced gross exposure and tighter portfolio risk cap |
| Crowded correlation spike | Positions move as one factor and sector concentration rises        | Cap correlated exposure; prioritize diversification       |

## 9.4 Portfolio constraints

- Cap initial risk per position and aggregate open risk.

- Limit sector and industry concentration because momentum portfolios can cluster in a small number of themes.

- Limit single-position market value even when the stop is unusually tight.

- Reject entries whose planned size is too large relative to average daily dollar volume.

- Use portfolio heat and realized correlation, not only the number of open positions, to judge diversification.

## 9.5 Exit hierarchy

**1.** Catastrophic or hard-risk exit: handles invalidation, severe gap risk, or broker/system failure.

**2.** Trend exit: closes the trade when the trailing channel or trend condition breaks.

**3.** Time exit: removes capital from a position that has failed to demonstrate expected continuation.

**4.** Portfolio-risk exit: reduces positions when aggregate exposure or drawdown exceeds predefined limits.

# 10. Backtesting and validation protocol

> **Most important methodological point**
>
> A convincing equity curve is not enough. The strategy must use point-in-time data, delisted securities, realistic execution, transaction costs, and a genuinely untouched out-of-sample period. Otherwise the result may be an artifact of the data or the research process.

## 10.1 Data requirements

| **Requirement**                        | **Why it matters**                                                                     |
|----------------------------------------|----------------------------------------------------------------------------------------|
| Survivorship-bias-free security master | Current index members omit failed and delisted companies, inflating historical results |
| Point-in-time corporate actions        | Splits, dividends, mergers, and symbol changes must not introduce future knowledge     |
| Delisting returns                      | Ignoring delisted positions can understate losses                                      |
| Reliable OHLCV and earnings timestamps | Daily breakouts and earnings gaps are highly sensitive to event and price alignment    |
| Bid-ask or slippage proxy              | Momentum entries often occur after price expansion, where market impact is nontrivial  |
| Point-in-time universe rules           | Market capitalization and liquidity screens must use values known on each date         |

## 10.2 Execution assumptions

- Do not fill a signal at the same closing price used to generate it unless a verifiable market-on-close process is modeled.

- Use next-open, volume-weighted, or stop-entry assumptions and compare results across execution models.

- Apply higher slippage to gaps, small stocks, and high participation rates.

- Model commissions even when nominal broker commissions are zero; spread and price impact remain.

- For stops, model gap-through behavior rather than assuming execution exactly at the stop price.

## 10.3 Experiment structure

**1.** Define one base model before inspecting performance.

**2.** Reserve a final holdout period that is not used for feature selection.

**3.** Use rolling or anchored walk-forward analysis for parameter and threshold evaluation.

**4.** Test across multiple market regimes, including major bear markets and sharp rebounds.

**5.** Measure results by subperiod, market-cap bucket, sector, and volatility regime.

**6.** Use bootstrap or trade-sequence resampling to estimate uncertainty around drawdown and expectancy.

**7.** Document every model change to prevent silent selection from hundreds of discarded variants.

## 10.4 Minimum performance report

| **Category**   | **Metrics**                                                                                           |
|----------------|-------------------------------------------------------------------------------------------------------|
| Return         | CAGR, annualized return, monthly return distribution, exposure-adjusted return                        |
| Risk           | Maximum drawdown, average drawdown, recovery time, volatility, downside deviation, tail loss          |
| Risk-adjusted  | Sharpe, Sortino, Calmar, return over average exposure                                                 |
| Trade quality  | Win rate, average win, average loss, payoff ratio, expectancy, profit factor, R-multiple distribution |
| Implementation | Turnover, holding period, trades per year, average spread/slippage, capacity proxy                    |
| Stability      | Rolling metrics, parameter surfaces, subperiod consistency, sector dependence, regime dependence      |

## 10.5 Parameter grid: start broad, then simplify

| **Parameter**         | **Initial test values**                                                  |
|-----------------------|--------------------------------------------------------------------------|
| Momentum lookback     | 6-1, 9-1, 12-1 months                                                    |
| Momentum percentile   | Top 10%, 15%, 20%, 30%                                                   |
| 52-week-high distance | 0%, 3%, 5%, 7%, 10%                                                      |
| Breakout lookback     | 10, 20, 40, 55 days                                                      |
| Market filter         | None; benchmark above 100-day; above 200-day; 50-day above 200-day       |
| Initial stop          | 1.5, 2, 2.5, 3 ATR; breakout-day low                                     |
| Trailing exit         | 5, 10, 20-day low; 20-day EMA; 3 ATR                                     |
| Risk per trade        | 0.20%, 0.35%, 0.50%, 0.75%                                               |
| Volume feature        | None; turnover percentile; 5/20 volume ratio; breakout volume percentile |

The goal is not to identify the single best cell in the grid. Prefer broad parameter regions with similar behavior. A strategy that works only at a 19-day breakout and fails at 18 or 20 days is probably capturing noise.

# 11. Failure modes and common mistakes

**Treating every new high as momentum.** A stock can make a short-term high while remaining weak over six or twelve months. Require genuine relative strength.

**Optimizing the breakout while ignoring the universe.** Microcaps and illiquid stocks can create spectacular historical results that cannot be executed.

**Using today’s index members historically.** This is a classic form of survivorship bias and can materially inflate performance.

**Assuming stop orders eliminate tail risk.** Stops can be skipped during overnight gaps, halts, and fast markets.

**Adding many filters at once.** Each extra rule creates another opportunity for data-mined improvement and reduces the number of independent observations.

**Forcing a high win rate.** Trend systems often accept frequent small losses. Optimizing for win rate can produce large hidden tail losses.

**Using volume as a slogan.** “High volume is bullish” is not a complete rule. Define the comparison window, normalization, and expected mechanism.

**Confusing a paper’s factor return with implementable personal performance.** Academic portfolios may be long-short, monthly rebalanced, capacity-intensive, or constructed before realistic taxes and slippage.

**Ignoring regime transitions.** Momentum can be particularly vulnerable when deeply depressed losers rebound violently.

**Continuously modifying live rules after losses.** A system cannot be evaluated when its rules change in response to every short-term result.

## Warning signs of overfitting

- Performance collapses when transaction costs are increased slightly.

- One year, sector, or handful of trades accounts for most profits.

- Small changes in lookback or threshold reverse the result.

- The final model contains many exceptions that were added after inspecting losing trades.

- Out-of-sample performance is materially weaker without a plausible structural reason.

- The backtest cannot be reproduced from a frozen code version and data snapshot.

# 12. Implementation roadmap

## Phase 1 - Build the benchmark

**1.** Create a survivorship-bias-free liquid-stock universe.

**2.** Implement a plain 20-day breakout with a 10-day-low exit and volatility-normalized position sizing.

**3.** Validate signal timing, corporate-action handling, fills, stops, and delistings before judging returns.

## Phase 2 - Add the evidence-backed selection layers

**1.** Add 12-1 month relative momentum and compare performance with the plain breakout.

**2.** Add 52-week-high proximity and measure incremental value.

**3.** Add the benchmark trend filter and portfolio volatility scaling.

**4.** Freeze the resulting Core system and run walk-forward and untouched holdout tests.

## Phase 3 - Test optional enhancements

**1.** Test volume features one at a time.

**2.** Test objective contraction features one at a time.

**3.** Test alternative exits and time stops while preserving the same signal set.

**4.** Build the earnings-gap continuation system as a separate module.

## Phase 4 - Paper trading and deployment controls

**1.** Run signals prospectively in paper mode with immutable daily logs.

**2.** Compare expected versus actual fills and revise the cost model before capital deployment.

**3.** Begin with a small risk budget and predefined escalation criteria, not discretionary confidence.

**4.** Define kill switches for data failure, order failure, abnormal slippage, portfolio drawdown, and market discontinuity.

**5.** Review the model on a fixed schedule; do not modify it after isolated wins or losses.

## Recommended first research specification

> **Version 0.1**
>
> US or European liquid common stocks; 12-1 month momentum top 15%; within 5% of 52-week high; close above prior 20-day high; stock above rising 50- and 200-day averages; benchmark above 200-day average; 2 ATR initial stop; 0.35% equity risk per trade; 10-day-low exit; maximum ten positions; realistic next-open execution. Compare directly with the same breakout system without momentum and high-proximity filters.

## Decision criteria before live use

| **Question**                                           | **Minimum evidence expected**                                                                  |
|--------------------------------------------------------|------------------------------------------------------------------------------------------------|
| Does the core model add value over the plain breakout? | Improvement should persist after costs and across multiple subperiods, not only in aggregate   |
| Is performance robust to parameters?                   | Neighboring lookbacks and thresholds should produce similar economic behavior                  |
| Is the edge diversified?                               | No single stock, sector, year, or regime should explain most profits                           |
| Are losses survivable?                                 | Historical and simulated drawdowns must fit the chosen risk budget with margin for model error |
| Can it be executed?                                    | Live or paper fills should be reasonably close to modeled fills                                |
| Can the process be followed?                           | Rules, data, orders, exceptions, and reviews must be operationally sustainable                 |

# 13. References

[1] Jegadeesh, N., and Titman, S. (1993). “Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency.” The Journal of Finance, 48(1), 65-91. [Source](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x)

[2] George, T. J., and Hwang, C.-Y. (2004). “The 52-Week High and Momentum Investing.” The Journal of Finance, 59(5), 2145-2176. [Source](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x)

[3] Moskowitz, T. J., Ooi, Y. H., and Pedersen, L. H. (2012). “Time Series Momentum.” Journal of Financial Economics, 104(2), 228-250. [Source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463)

[4] Lee, C. M. C., and Swaminathan, B. (2000). “Price Momentum and Trading Volume.” The Journal of Finance, 55(5), 2017-2069. [Source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589)

[5] Daniel, K., and Moskowitz, T. J. (2016). “Momentum Crashes.” Journal of Financial Economics, 122(2), 221-247. [Source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227)

[6] Barroso, P., and Santa-Clara, P. (2015). “Momentum Has Its Moments.” Journal of Financial Economics, 116(1), 111-120. [Source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429)

[7] Hurst, B., Ooi, Y. H., and Pedersen, L. H. (2017). “A Century of Evidence on Trend-Following Investing.” The Journal of Portfolio Management, 44(1), 15-29. [Source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)

[8] Park, C.-H., and Irwin, S. H. (2007). “What Do We Know About the Profitability of Technical Analysis?” Journal of Economic Surveys, 21(4), 786-826. [Source](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-6419.2007.00519.x)

[9] Fink, J. (2021). “A Review of the Post-Earnings-Announcement Drift.” Journal of Behavioral and Experimental Finance, 29, 100446. [Source](https://www.sciencedirect.com/science/article/pii/S2214635020303750)

[10] Martineau, C. (2021). “Rest in Peace Post-Earnings Announcement Drift.” Working paper. [Source](https://ideas.repec.org/p/osf/socarx/z7k3p.html)

## Interpretive note

This report synthesizes the findings above into a practical research design. The specific filters, thresholds, and execution rules are the report author’s proposed operationalization and should not be attributed directly to the cited papers unless explicitly stated. Historical evidence can decay, implementation costs can erase theoretical returns, and no backtest can eliminate uncertainty about future performance.

*Prepared from the cited academic abstracts, published-paper metadata, and the research review conducted in July 2026.*
