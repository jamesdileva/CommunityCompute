"""Economics research package (Sprint 34).

The network's economics are *measured*, not assumed: this package turns the
data the prototype already records (per-unit execution time, verified-unit
volume, uptime, verification overhead) plus a small, clearly-labelled set of
cost assumptions (electricity price, hardware power/price/life, bandwidth,
infrastructure, centralized list prices) into a cost-per-useful-compute model.

`model` holds the pure math; `measure` extracts the measured inputs from the
database; `report` composes the two into one auditable document.
"""
