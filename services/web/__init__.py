# services/web/__init__.py
"""
Web Services Package - Browser Automation and Scraping Utilities

This package provides reusable utilities for web automation, scraping, and
data extraction from websites that don't provide APIs. It features a new
generic architecture that separates site-specific logic from reusable components.

Package Structure:
- base.py: Abstract interfaces and configuration classes
- generic_browser.py: Generic browser manager with configurable behavior
- generic_table.py: Generic table scraper with configurable extraction
- configs/: Site-specific configuration modules (OMIRL, etc.)
- adapters/: Site-specific adapters that combine generic components
- compat.py: Compatibility layer for existing code

Legacy Structure (maintained for compatibility):
- browser.py: Original Playwright browser lifecycle (OMIRL-specific)
- table_scraper.py: Original HTML table extraction (OMIRL-specific)

Used by:
- tools/omirl/: Primary consumer for OMIRL web scraping (via new architecture)
- Future tools: Any website with proper configuration

Design Philosophy:
- Generic components with site-specific configuration
- Respectful scraping with rate limiting
- Robust error handling for network/DOM issues
- Backward compatibility with existing code
- Modular and reusable architecture

Migration Path:
1. Use compat.py for immediate compatibility
2. Gradually migrate to new architecture
3. Eventually deprecate legacy modules
"""

# New architecture exports
from .base import (
    BrowserConfig, 
    TableConfig, 
    SiteConfig,
    IBrowserManager,
    ITableScraper, 
    ISiteAdapter
)

from .generic_browser import GenericBrowserManager, create_browser_manager
from .generic_table import GenericTableScraper, create_table_scraper

from .configs import (
    create_omirl_site_config,
    create_omirl_browser_config,
    create_omirl_table_config
)

from .adapters import create_omirl_adapter, OMIRLAdapter

__all__ = [
    # New architecture
    'BrowserConfig', 'TableConfig', 'SiteConfig',
    'IBrowserManager', 'ITableScraper', 'ISiteAdapter',
    'GenericBrowserManager', 'create_browser_manager',
    'GenericTableScraper', 'create_table_scraper',
    'create_omirl_site_config', 'create_omirl_browser_config', 'create_omirl_table_config',
    'create_omirl_adapter', 'OMIRLAdapter',
]