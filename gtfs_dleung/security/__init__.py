"""Security primitives — input validation, inbound rate limiting, etc.

The outbound polite-consumer limiter lives under ``gtfs_dleung.fetcher.rate_limit``
rather than here; the two are split by direction of traffic (outbound = MBTA-side
neighbour-politeness, inbound = our-app-side abuse protection).
"""
