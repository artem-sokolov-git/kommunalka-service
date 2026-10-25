# Domain

Frozen `slots` dataclasses, no framework imports. Entities reference each other by UUID. Value
objects (`DateRange`, `Unit`, `MeteredBillLine`/`FixedBillLine`) live in `value_objects.py`,
errors (all subclass `DomainError`) in `exceptions.py`. Rules that need several entities are
plain functions next to the entity: `ensure_unique_*`, `ensure_no_overlap`, `ensure_not_billed`,
`next_reading`, `readings_for_month`. `services/billing.py::calculate_bill` builds a `Bill` from
meters, readings and tariffs.

Money and readings are `Decimal`, rounded to kopecks with `ROUND_HALF_UP`.

## Billing rules

A reading taken in month M closes month M−1 (`Reading.billing_period`); one reading per meter
and month (`readings.billing_month` column enforces it); the first reading is a baseline.
Tariffs are `TariffPeriod`s with optional `valid_to` (open-ended); for unmetered services the
price is a monthly amount added to bills automatically unless `fixed_amounts` overrides it.
A price change (`change_price` → `next_tariff_period`) starts on the 1st of a month after the
latest price, closes the open period the day before and can't touch billed months;
`undo_price_change` removes the latest price and reopens the previous one unless a bill uses it.
A bill is a whole calendar month; once issued, readings of that month can't change.
