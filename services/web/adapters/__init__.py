"""
Web Service Adapters

This package contains site-specific adapters that combine generic web scraping
components with site-specific configurations to provide high-level data extraction
interfaces.

Available adapters:
- omirl_adapter: Adapter for OMIRL (Liguria meteorological data)

Usage:
    from services.web.adapters.omirl_adapter import create_omirl_adapter
    
    adapter = create_omirl_adapter()
    data = await adapter.fetch_data("valori_stazioni", {"sensor_type": "Precipitazione"})
"""

"""OMIRL web services adapters."""

from .omirl_adapter import OMIRLAdapter, get_omirl_adapter

__all__ = ["OMIRLAdapter", "get_omirl_adapter"]
