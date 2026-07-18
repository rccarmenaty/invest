# Delta for Sharadar Market Context Generator

## MODIFIED Requirements

### Requirement: Configurable point-in-time liquidity screen

The generator SHALL apply a daily, parameterized, no-look-ahead screen. Core defaults MUST remain price >= $10, median 20-bar dollar volume >= $10M, and 252 observed bars. Dollar volume MUST multiply adjusted close by canonical volume using exact `Decimal` arithmetic through median and threshold evaluation. AUM, ADV-fraction, and price-impact rules MUST remain excluded.
(Previously: Fractional volume and exact Decimal arithmetic were not explicit.)

#### Scenario: Apply Core defaults

- GIVEN a listed primary common stock with 252 bars
- WHEN its current price and exact trailing 20-bar median dollar volume meet Core defaults
- THEN its current date MUST be eligible

#### Scenario: Reject insufficient or failing history

- GIVEN insufficient history, price, or rolling volume
- WHEN the screen evaluates that date
- THEN it MUST produce an ineligible date without using later bars

#### Scenario: Retain fractional liquidity at the threshold

- GIVEN fractional volumes whose exact products pass the threshold but truncated products fail it
- WHEN the liquidity screen evaluates the date
- THEN the date MUST pass the liquidity threshold
- AND no intermediate value MAY be converted to an integer or binary floating-point value
