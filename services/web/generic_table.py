"""
Generic Table Scraper Implementation

This module provides a generic, configurable table scraper that can extract
data from HTML tables on any website. It separates table parsing logic from
site-specific configurations.

Features:
- Configurable table and element selectors
- Smart table detection by headers
- Flexible data extraction and validation
- Support for different table structures
- Error recovery and fallback mechanisms

Usage:
    config = TableConfig(
        expected_headers=["Name", "Code", "City"],
        required_fields=["Name", "Code"]
    )
    scraper = GenericTableScraper()
    data = await scraper.extract_table_data(page, config)
"""

import asyncio
from typing import List, Dict, Any, Optional
from playwright.async_api import Page

from .base import ITableScraper, TableConfig, TableExtractionError


class GenericTableScraper(ITableScraper):
    """Generic table scraper with configurable behavior"""
    
    def __init__(self):
        pass
        
    async def extract_table_data(
        self, 
        page: Page, 
        table_config: Optional[TableConfig] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from HTML tables on the page"""
        config = table_config or TableConfig()
        
        try:
            print("📊 Starting generic table data extraction...")
            
            # Wait for content to load if specified
            if config.wait_for_content_ms > 0:
                await page.wait_for_timeout(config.wait_for_content_ms)
            
            # Find the target table
            table_index = None
            
            if config.expected_headers:
                # Try to find table by headers
                table_index = await self.find_table_by_headers(page, config.expected_headers)
                if table_index is not None:
                    print(f"🎯 Found table with expected headers at index {table_index}")
            
            if table_index is None and config.table_index is not None:
                # Fallback to specified table index
                table_index = config.table_index
                print(f"🔄 Using fallback table index {table_index}")
            
            if table_index is not None:
                # Extract from specific table
                return await self.extract_table_by_index(page, table_index, config)
            else:
                # Extract from first table found
                tables = await page.query_selector_all(config.table_selector)
                if not tables:
                    raise TableExtractionError("No tables found on page")
                
                print(f"📋 Extracting from first table (found {len(tables)} tables)")
                return await self.extract_table_by_index(page, 0, config)
                
        except Exception as e:
            print(f"❌ Error extracting table data: {e}")
            raise TableExtractionError(f"Failed to extract table data: {e}")
            
    async def find_table_by_headers(
        self, 
        page: Page, 
        expected_headers: List[str]
    ) -> Optional[int]:
        """Find table index by matching expected headers"""
        try:
            tables = await page.query_selector_all("table")
            print(f"🔍 Searching through {len(tables)} tables for headers: {expected_headers}")
            
            for i, table in enumerate(tables):
                header_cells = await table.query_selector_all("thead tr th, tr:first-child th, tr:first-child td")
                if header_cells:
                    headers = []
                    for cell in header_cells:
                        header_text = await cell.inner_text()
                        headers.append(header_text.strip())
                    
                    print(f"📋 Table {i} headers: {headers}")
                    
                    # Check if expected headers are present
                    matches = sum(1 for expected in expected_headers if expected in headers)
                    if matches >= len(expected_headers) * 0.5:  # At least 50% match
                        print(f"✅ Table {i} matches expected headers ({matches}/{len(expected_headers)} found)")
                        return i
                        
            print("⚠️  No table found with matching headers")
            return None
            
        except Exception as e:
            print(f"❌ Error searching for table by headers: {e}")
            return None
            
    async def extract_table_by_index(
        self, 
        page: Page, 
        table_index: int,
        table_config: Optional[TableConfig] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from a specific table by index"""
        config = table_config or TableConfig()
        
        try:
            print(f"📊 Extracting data from table {table_index}...")
            
            # Get all tables
            tables = await page.query_selector_all(config.table_selector)
            
            if table_index >= len(tables):
                raise TableExtractionError(f"Table {table_index} not found (only {len(tables)} tables available)")
            
            target_table = tables[table_index]
            
            # Extract headers
            header_cells = await target_table.query_selector_all(config.header_selector)
            headers = []
            for cell in header_cells:
                header_text = await cell.inner_text()
                headers.append(header_text.strip())
                
            if not headers:
                raise TableExtractionError(f"No headers found in table {table_index}")
                
            print(f"📋 Table {table_index} headers: {headers}")
            
            # Extract data rows
            body_rows = await target_table.query_selector_all("tbody tr")
            if not body_rows:
                # Fallback: look for direct tr elements (skip header row)
                all_rows = await target_table.query_selector_all("tr")
                body_rows = all_rows[1:] if len(all_rows) > 1 else []
                
            print(f"🔢 Found {len(body_rows)} data rows")
            
            table_data = []
            
            for i, row in enumerate(body_rows):
                cells = await row.query_selector_all(config.cell_selector)
                
                if len(cells) > 0:
                    row_data = {}
                    
                    # Map each cell to its corresponding header
                    for j, header in enumerate(headers):
                        if j < len(cells):
                            cell_text = await cells[j].inner_text()
                            row_data[header] = cell_text.strip()
                        else:
                            row_data[header] = ""
                    
                    # Validate row data if required fields are specified
                    if self._validate_row_data(row_data, config):
                        table_data.append(row_data)
                        if i < 3:  # Show first few for debugging
                            print(f"✅ Row {i}: {dict(list(row_data.items())[:3])}...")
                    else:
                        if i < 10:  # Show first few rejections for debugging
                            print(f"⚠️  Row {i} skipped - validation failed")
                else:
                    if config.skip_empty_rows:
                        continue
                    else:
                        print(f"⚠️  Row {i} has no cells")
                        
            print(f"📈 Successfully extracted {len(table_data)} valid records")
            return table_data
            
        except Exception as e:
            print(f"❌ Error extracting table {table_index} data: {e}")
            raise TableExtractionError(f"Failed to extract table {table_index}: {e}")
    
    def _validate_row_data(self, row_data: Dict[str, Any], config: TableConfig) -> bool:
        """Validate row data against configuration requirements"""
        # Check required fields
        if config.required_fields:
            for field in config.required_fields:
                if field not in row_data or not row_data[field].strip():
                    return False
        
        # Skip empty rows if configured
        if config.skip_empty_rows:
            # Check if all fields are empty
            non_empty_values = [v for v in row_data.values() if v and v.strip()]
            if not non_empty_values:
                return False
        
        return True


# Factory function for easy instantiation
def create_table_scraper() -> GenericTableScraper:
    """Factory function to create a table scraper"""
    return GenericTableScraper()
