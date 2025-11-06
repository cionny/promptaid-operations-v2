"""
OMIRL-Specific Configuration

This module contains OMIRL-specific browser automation configuration settings
for Playwright-based web scraping. It loads shared business data (sensor types,
URLs, table structures) from parameters.yaml to avoid duplication.

The configuration includes:
- Browser settings optimized for OMIRL (Italian locale, timeouts)
- CSS selectors for UI elements
- AngularJS-specific timing and wait strategies
- Playwright-specific configurations

Shared data (sensor types, URLs, table indices, provinces, zones) is loaded
from tools/omirl/config/parameters.yaml at initialization time.

This maintains a clear separation of concerns:
- omirl_config.py: HOW to scrape (technical browser automation)
- parameters.yaml: WHAT to validate (business rules and data definitions)
"""

import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from ..base import BrowserConfig, TableConfig, SiteConfig


@dataclass
class OMIRLBrowserConfig(BrowserConfig):
    """OMIRL-optimized browser configuration"""
    
    def __init__(self):
        super().__init__(
            # OMIRL-specific locale settings
            locale="it-IT",
            timezone_id="Europe/Rome",
            
            # Extended timeouts for AngularJS application
            default_timeout=30000,
            navigation_timeout=60000,  # OMIRL's AngularJS is slow
            
            # OMIRL-respectful rate limiting
            rate_limit_ms=500,
            
            # Italian locale headers
            extra_headers={
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
            },
            
            # Desktop viewport for OMIRL
            viewport={"width": 1920, "height": 1080},
            
            # User agent to avoid bot detection
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )


@dataclass
class OMIRLTableConfig(TableConfig):
    """OMIRL-specific table extraction configuration"""
    
    def __init__(self, table_type: str = "valori_stazioni"):
        knowledge = get_omirl_knowledge()
        
        if table_type == "valori_stazioni":
            table_index = knowledge.get_table_index("valori_stazioni")
            super().__init__(
                # Discovered table structure for station data
                expected_headers=["Nome", "Codice", "Comune", "Provincia"],
                table_index=table_index,
                required_fields=["Nome", "Codice"],
                
                # AngularJS timing requirements
                wait_after_navigation_ms=3000,  # Wait for AngularJS to initialize
                wait_for_content_ms=5000,       # Wait for table data to load
            )
        elif table_type == "massimi_precipitazioni_zona":
            table_index = knowledge.get_table_index("massimi_precipitazione", "zona_allerta")
            super().__init__(
                table_index=table_index,
                wait_after_navigation_ms=3000,
                wait_for_content_ms=5000,
            )
        elif table_type == "massimi_precipitazioni_province":
            table_index = knowledge.get_table_index("massimi_precipitazione", "province")
            super().__init__(
                table_index=table_index,
                wait_after_navigation_ms=3000,
                wait_for_content_ms=5000,
            )
        else:
            super().__init__()


class OMIRLKnowledge:
    """
    Container for OMIRL-specific scraping knowledge.
    
    Loads shared business data from parameters.yaml at initialization.
    Contains only scraping-specific technical details (selectors, timing).
    """
    
    def __init__(self, parameters_path: Optional[Path] = None):
        """
        Initialize OMIRL knowledge by loading from parameters.yaml
        
        Args:
            parameters_path: Optional path to parameters.yaml. If None, uses default location.
        """
        if parameters_path is None:
            # Default: tools/omirl/config/parameters.yaml
            parameters_path = Path(__file__).parent.parent.parent.parent / "tools" / "omirl" / "config" / "parameters.yaml"
        
        self._load_parameters(parameters_path)
        
    def _load_parameters(self, parameters_path: Path):
        """Load shared data from parameters.yaml"""
        try:
            with open(parameters_path, 'r', encoding='utf-8') as f:
                params = yaml.safe_load(f)
            
            # Base URL (constant, not in YAML since it's scraping-specific)
            self.BASE_URL = "https://omirl.regione.liguria.it"
            
            # Load URLs from parameters.yaml
            task_urls = params.get('task_urls', {})
            self.URLS = {}
            for category in task_urls.values():
                if isinstance(category, dict):
                    self.URLS.update(category)
            
            # Convert full URLs to hash paths for consistency with old code
            for task, url in self.URLS.items():
                if url.startswith("https://omirl.regione.liguria.it"):
                    self.URLS[task] = url.replace("https://omirl.regione.liguria.it", "")
            
            # Load sensor types from parameters.yaml and create index mapping
            sensor_types = params.get('sensor_types', [])
            self.SENSOR_TYPE_MAPPING = {i: sensor_type for i, sensor_type in enumerate(sensor_types)}
            self.SENSOR_NAME_TO_INDEX = {v: k for k, v in self.SENSOR_TYPE_MAPPING.items()}
            
            # Load table structure from parameters.yaml
            table_structure = params.get('table_structure', {})
            self._table_structure = table_structure
            
            # Time periods (for validation)
            self.TIME_PERIODS = params.get('time_periods', [])
            
            # Store raw parameters for access by other components
            self._parameters = params
            
        except FileNotFoundError:
            raise RuntimeError(f"Parameters file not found: {parameters_path}")
        except Exception as e:
            raise RuntimeError(f"Error loading parameters: {e}")
    
    # CSS Selectors (scraping-specific, not in parameters.yaml)
    SELECTORS = {
        "sensor_type_filter": "select#stationType",
        "station_table": "table:nth-of-type(5)",  # Table index 4 (0-based = 5th table)
        "zona_allerta_table": "table:nth-of-type(5)",  # Table index 4
        "province_table": "table:nth-of-type(6)"       # Table index 5
    }
    
    # Timing patterns for AngularJS (scraping-specific, not in parameters.yaml)
    TIMING = {
        "post_navigation_wait": 3000,    # Wait after navigation for AngularJS init
        "table_load_wait": 5000,         # Wait for AngularJS to load table data
        "network_idle_timeout": 8000,    # Timeout for network idle state
        "filter_apply_wait": 2000,       # Wait after applying filters
        "rate_limit_delay": 500          # Minimum delay between requests
    }
    
    # Expected data structure for validation (scraping-specific)
    EXPECTED_STATION_FIELDS = ["Nome", "Codice", "Comune", "Provincia"]
    
    def get_table_index(self, task: str, table_type: str = "default") -> int:
        """
        Get table index for a specific task from parameters.yaml
        
        Args:
            task: Task name (valori_stazioni, massimi_precipitazione, livelli_idrometrici)
            table_type: Type of table (default, zona_allerta, province, etc.)
        
        Returns:
            Table index (0-based)
        """
        task_structure = self._table_structure.get(task, {})
        
        if task == "valori_stazioni":
            return task_structure.get("station_table_index", 4)
        elif task == "massimi_precipitazione":
            if table_type == "zona_allerta":
                return task_structure.get("zona_allerta_table_index", 4)
            elif table_type == "province":
                return task_structure.get("province_table_index", 5)
        elif task == "livelli_idrometrici":
            zona_map = task_structure.get("zona_table_map", {})
            # Return the zona map for livelli_idrometrici
            if table_type in zona_map.values():
                # Reverse lookup: find table index by zona
                for idx, zona in zona_map.items():
                    if zona == table_type:
                        return int(idx)
            return zona_map  # Return the whole map if no specific match
        
        return 4  # Default fallback


# Global singleton instance
_omirl_knowledge_instance = None

def get_omirl_knowledge() -> OMIRLKnowledge:
    """Get or create global OMIRLKnowledge instance"""
    global _omirl_knowledge_instance
    if _omirl_knowledge_instance is None:
        _omirl_knowledge_instance = OMIRLKnowledge()
    return _omirl_knowledge_instance


def create_omirl_site_config() -> SiteConfig:
    """Create complete OMIRL site configuration"""
    knowledge = get_omirl_knowledge()
    
    return SiteConfig(
        base_url=knowledge.BASE_URL,
        browser_config=OMIRLBrowserConfig(),
        table_config=OMIRLTableConfig(),
        urls=knowledge.URLS,
        selectors=knowledge.SELECTORS,
        data_mappings={
            "sensor_types": knowledge.SENSOR_TYPE_MAPPING,
            "sensor_name_to_index": knowledge.SENSOR_NAME_TO_INDEX,
            "timing": knowledge.TIMING,
            "expected_fields": {
                "stations": knowledge.EXPECTED_STATION_FIELDS,
                "time_periods": knowledge.TIME_PERIODS
            }
        }
    )


def create_omirl_browser_config() -> OMIRLBrowserConfig:
    """Factory function for OMIRL browser configuration"""
    return OMIRLBrowserConfig()


def create_omirl_table_config(table_type: str = "valori_stazioni") -> OMIRLTableConfig:
    """Factory function for OMIRL table configuration"""
    return OMIRLTableConfig(table_type)
