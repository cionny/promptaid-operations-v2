# services/data/__init__.py
"""
Data Services Package - Shared Utilities for External Data Sources

This package provides reusable utilities for fetching, caching, and processing
data from external sources. These functions are designed to be tool-agnostic
and handle common data integration challenges.

Package Structure:
- csv_fetch.py: HTTP client for CSV downloads with domain validation
- cache.py: TTL-based caching system to reduce external API load
- html_table.py: HTML table parsing for fallback scenarios

Used by:
- tools/omirl/: Primary consumer for OMIRL data
- Future tools (ARPAL, Motorways): Will reuse these utilities

Design Philosophy:
- Pure functions with clear input/output contracts
- No hidden state or side effects
- Graceful error handling (return errors, don't raise)
- Security-first (domain allowlisting, input validation)
"""