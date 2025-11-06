"""
Web Service Configurations

This package contains site-specific configurations for web scraping services.
Each configuration module contains all the knowledge and settings needed to
scrape a particular website effectively.

Available configurations:
- omirl_config: Configuration for OMIRL (Liguria meteorological data)

Usage:
    from services.web.configs.omirl_config import create_omirl_site_config
    
    config = create_omirl_site_config()
    # Use config with generic browser and table scraper components
"""

from .omirl_config import (
    create_omirl_site_config,
    create_omirl_browser_config, 
    create_omirl_table_config,
    OMIRLKnowledge,
    get_omirl_knowledge
)

__all__ = [
    'create_omirl_site_config',
    'create_omirl_browser_config',
    'create_omirl_table_config', 
    'OMIRLKnowledge',
    'get_omirl_knowledge'
]
