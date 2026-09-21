# What a real deployment still needs

The repository deliberately separates an academic demonstration from actions
that would move money or electricity. None of the three integrations below can
be honestly marked complete without an external partner and credentials.

## Charging-station availability and booking

Current state: nine Austrian station locations are preloaded. Availability is
simulated through `POST /stations/{id}/status`; the API records the source and
timestamp. A plan is **not** a physical charger reservation.

Required from an operator: station identifiers matching the catalog, an
authenticated availability/booking interface, update cadence, connector-level
status definitions, and cancellation rules. Integration acceptance test: a
status change on a real charger appears in Smart EV, a booking is confirmed by
the operator, and duplicate bookings are rejected.

## Real advance payment

Current state: card information is not stored; checkout creates only a demo
payment record and reference. No funds move.

Required: choice of payment service provider, merchant account, sandbox and
production credentials, webhook signing secret, currency/tax policy, refund
flow, and a policy for payment failure after booking. Integration acceptance
test: signed provider webhook settles one booking exactly once; failed or
cancelled payments cannot confirm it; refunds are recorded consistently.

## Physical V2G export and reward

Current state: optimizer simulates a discharge slot and reward. Wallet credit
is not a measured energy settlement.

Required: bidirectional EV and charger, charger control interface, measured
meter readings, grid/aggregator participation, tariff and settlement contract,
and explicit user consent. Integration acceptance test: measured exported kWh
matches a physical session and the reward is calculated from an agreed tariff,
not merely a forecasted wholesale price.

## Current-model validation

The Austrian 2026 feed is available through Energy-Charts, but the deployed
model was trained on 2015-2018 OPSD data. Collect a current continuous period,
run a forward chronological backtest, compare with a recent seasonal baseline,
and retrain only if the new model passes predefined gates. Do not present
historical MAE as current accuracy.
