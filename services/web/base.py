"""
Web Services Base Classes and Interfaces

This module defines the abstract base classes and interfaces for web scraping
services. It provides a foundation for implementing site-specific scrapers
while maintaining a consistent API.

The design separates:
- Generic browser management (lifecycle, navigation, waits)
- Generic table extraction (parsing, data cleaning, validation)
- Site-specific configuration (URLs, selectors, timing, locales)
- Site-specific business logic (filtering, data transformation)

This allows for:
- Reusable generic components across different websites
- Easy testing with mocked configurations
- Clear separation of concerns
- Backward compatibility with existing implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from playwright.async_api import Page, BrowserContext
import asyncio


@dataclass
class BrowserConfig:
    """Configuration for browser behavior and settings"""
    
    # Browser settings
    headless: bool = True
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    locale: str = "en-US"
    timezone_id: str = "UTC"
    user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Timeout settings (in milliseconds)
    default_timeout: int = 30000
    navigation_timeout: int = 60000
    
    # Rate limiting
    rate_limit_ms: int = 500
    
    # Custom headers
    extra_headers: Dict[str, str] = field(default_factory=dict)
    
    # Browser args
    browser_args: List[str] = field(default_factory=lambda: [
        '--no-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-features=VizDisplayCompositor'
    ])


@dataclass
class TableConfig:
    """Configuration for table extraction behavior"""
    
    # Target selectors
    table_selector: str = "table"
    header_selector: str = "thead tr th, tr:first-child th, tr:first-child td"
    row_selector: str = "tbody tr, tr"
    cell_selector: str = "td, th"
    
    # Table identification
    expected_headers: List[str] = field(default_factory=list)
    table_index: Optional[int] = None
    
    # Data validation
    required_fields: List[str] = field(default_factory=list)
    skip_empty_rows: bool = True
    
    # Timing
    wait_after_navigation_ms: int = 2000
    wait_for_content_ms: int = 3000


@dataclass
class SiteConfig:
    """Configuration for a specific website"""
    
    base_url: str
    browser_config: BrowserConfig
    table_config: TableConfig
    
    # Site-specific URLs
    urls: Dict[str, str] = field(default_factory=dict)
    
    # Site-specific selectors
    selectors: Dict[str, str] = field(default_factory=dict)
    
    # Site-specific data mappings
    data_mappings: Dict[str, Any] = field(default_factory=dict)


class IBrowserManager(ABC):
    """Abstract interface for browser management"""
    
    @abstractmethod
    async def get_context(self, context_id: str = "default") -> BrowserContext:
        """Get or create a browser context"""
        pass
    
    @abstractmethod
    async def navigate_with_retry(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with retry logic"""
        pass
    
    @abstractmethod
    async def apply_rate_limiting(self, delay_ms: Optional[int] = None):
        """Apply rate limiting delay"""
        pass
    
    @abstractmethod
    async def close_context(self, context_id: str = "default"):
        """Close a specific browser context"""
        pass
    
    @abstractmethod
    async def close_all(self):
        """Close all browser resources"""
        pass


class ITableScraper(ABC):
    """Abstract interface for table scraping"""
    
    @abstractmethod
    async def extract_table_data(
        self, 
        page: Page, 
        table_config: Optional[TableConfig] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from HTML tables on the page"""
        pass
    
    @abstractmethod
    async def find_table_by_headers(
        self, 
        page: Page, 
        expected_headers: List[str]
    ) -> Optional[int]:
        """Find table index by matching expected headers"""
        pass
    
    @abstractmethod
    async def extract_table_by_index(
        self, 
        page: Page, 
        table_index: int,
        table_config: Optional[TableConfig] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from a specific table by index"""
        pass


class ISiteAdapter(ABC):
    """Abstract interface for site-specific adapters"""
    
    @abstractmethod
    async def fetch_data(
        self, 
        data_type: str, 
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Fetch data of a specific type with optional filters"""
        pass
    
    @abstractmethod
    def get_supported_data_types(self) -> List[str]:
        """Get list of supported data types"""
        pass
    
    @abstractmethod
    def validate_filters(
        self, 
        data_type: str, 
        filters: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate filters for a data type"""
        pass


class WebScrapingError(Exception):
    """Base exception for web scraping errors"""
    pass


class NavigationError(WebScrapingError):
    """Exception for navigation failures"""
    pass


class TableExtractionError(WebScrapingError):
    """Exception for table extraction failures"""
    pass


class ConfigurationError(WebScrapingError):
    """Exception for configuration errors"""
    pass
