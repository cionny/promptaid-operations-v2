"""
OMIRL Adapter for operations-v2

Native scraper - no v1 dependencies.
"""

import re
import asyncio
from typing import List
from playwright.async_api import ElementHandle

from agents.meteo.models import RawHydroStation, RawRainData
from services.web.generic_browser import GenericBrowserManager
from services.web.base import BrowserConfig


class OMIRLAdapter:
    """Native OMIRL scraper - builds Pydantic models directly from DOM."""
    
    HYDRO_URL = "https://omirl.regione.liguria.it/#/alertzones"
    # Zone letters (A-E): A=Marittimi Ponente, B=Marittimi Centro, C=Marittimi Levante, D=Padani Ponente, E=Padani Levante
    HYDRO_TABLE_MAP = {4: "A", 5: "B", 6: "C", 7: "D", 8: "E"}
    RAIN_URL = "https://omirl.regione.liguria.it/#/maxtable"
    RAIN_TABLE_MAP = {4: "zona", 5: "provincia"}
    
    async def fetch_livelli_idrometrici(self) -> List[RawHydroStation]:
        """
        Scrape hydrometric levels from OMIRL alertzones page.
        Returns Pydantic models directly - no intermediate dicts.
        """
        config = BrowserConfig(
            locale="it-IT",
            timezone_id="Europe/Rome",
            headless=True
        )
        browser_manager = GenericBrowserManager(config)
        
        try:
            context = await browser_manager.get_context("livelli_idro")
            page = await context.new_page()
            
            print(f"\n🌊 Scraping {self.HYDRO_URL}")
            await browser_manager.navigate_with_retry(page, self.HYDRO_URL)
            
            # Wait for AngularJS rendering
            await page.wait_for_timeout(3000)
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass  # Continue anyway
            
            await page.wait_for_timeout(2000)
            
            # Get all tables
            tables = await page.query_selector_all("table")
            print(f"📋 Found {len(tables)} tables")
            
            # Parse zona tables (indices 4-8)
            all_stations = []
            for table_idx, zona in self.HYDRO_TABLE_MAP.items():
                if table_idx >= len(tables):
                    continue
                stations = await self._parse_hydro_table(tables[table_idx], zona)
                print(f"  Zona {zona}: {len(stations)} stations")
                all_stations.extend(stations)
            
            print(f"✅ Scraped {len(all_stations)} stations")
            return all_stations
            
        finally:
            # IMPORTANT: Close ALL browser resources to prevent hanging
            await browser_manager.close_all()
    
    async def _parse_hydro_table(self, table: ElementHandle, zona: str) -> List[RawHydroStation]:
        """Parse table rows directly into Pydantic models."""
        stations = []
        rows = await table.query_selector_all('tr')
        
        for row in rows[1:]:  # Skip header
            cells = await row.query_selector_all('td, th')
            if len(cells) < 9:
                continue
            
            # Extract text from cells
            texts = [await cell.inner_text() for cell in cells]
            texts = [t.strip() for t in texts]
            
            # Parse levels (Italian format: "2,34" → 2.34)
            def parse_level(text: str) -> float:
                if not text or text == '-':
                    return None
                try:
                    return float(text.replace(',', '.').replace('m', '').strip())
                except:
                    return None
            
            stations.append(RawHydroStation(
                localita=texts[0],  # Keep raw format: "Tiglieto [TIGLT]"
                provincia=texts[1],
                comune=texts[2],
                bacino=texts[3],
                corso_acqua=texts[4],
                max_24h=parse_level(texts[5]),
                max_24h_time=texts[6],
                last_level=parse_level(texts[7]),
                reference_time=texts[8],
                zona_allerta=zona
            ))
        
        return stations


    async def fetch_precipitazioni(self) -> List[RawRainData]:
        """
        Scrape precipitation data from OMIRL maxtable page.
        Returns both zone and province aggregations.
        """
        config = BrowserConfig(
            locale="it-IT",
            timezone_id="Europe/Rome",
            headless=True
        )
        browser_manager = GenericBrowserManager(config)
        
        try:
            context = await browser_manager.get_context("precipitazioni")
            page = await context.new_page()
            
            print(f"\n🌧️  Scraping {self.RAIN_URL}")
            await browser_manager.navigate_with_retry(page, self.RAIN_URL)
            
            # Wait for AngularJS rendering
            await page.wait_for_timeout(3000)
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            
            await page.wait_for_timeout(2000)
            
            # Get all tables
            tables = await page.query_selector_all("table")
            print(f"📋 Found {len(tables)} tables")
            
            all_data = []
            
            # Parse rain tables using map
            for table_idx, location_type in self.RAIN_TABLE_MAP.items():
                if table_idx >= len(tables):
                    continue
                table_data = await self._parse_rain_table(tables[table_idx], location_type)
                print(f"  {location_type.capitalize()}: {len(table_data)} entries")
                all_data.extend(table_data)
            
            print(f"✅ Scraped {len(all_data)} rain data entries")
            return all_data
            
        finally:
            await browser_manager.close_all()
    
    
    async def _parse_rain_table(self, table: ElementHandle, location_type: str) -> List[RawRainData]:
        """Parse rain table rows into Pydantic models - one entry per time period."""
        data = []
        rows = await table.query_selector_all('tr')
        
        if len(rows) < 2:
            return data
        
        # Extract header to get time periods
        header_cells = await rows[0].query_selector_all('th')
        headers = [await cell.inner_text() for cell in header_cells]
        headers = [h.strip() for h in headers]
        
        # Time periods start from column 1 (column 0 is "Max (mm)")
        time_periods = headers[1:]  # e.g., ["5'", "15'", "30'", "1h", "3h", ...]
        
        # Parse data rows (skip header)
        for row in rows[1:]:
            cells = await row.query_selector_all('td, th')
            if len(cells) < 2:
                continue
            
            texts = [await cell.inner_text() for cell in cells]
            texts = [t.strip() for t in texts]
            
            location = texts[0]
            if not location:
                continue
            
            # Parse each time period cell: "0.4 [09:20] Pieve di Teco"
            for i, period in enumerate(time_periods):
                if i + 1 >= len(texts):
                    continue
                
                cell_text = texts[i + 1]
                if not cell_text or cell_text == '-':
                    continue
                
                try:
                    # Split by brackets to extract: "0.4 [09:20] Pieve di Teco"
                    # Format: value [time] station
                    match = re.match(r'([\d,\.]+)\s*\[([^\]]+)\]\s*(.+)', cell_text)
                    if not match:
                        continue
                    
                    max_mm_str, max_time, max_station = match.groups()
                    
                    # Parse accumulation (handle Italian decimal format)
                    max_mm_str = max_mm_str.replace('\xa0', '').replace(',', '.').strip()
                    max_mm = float(max_mm_str)
                    
                    data.append(RawRainData(
                        location=location,
                        location_type=location_type,
                        time_period=period,
                        max_mm=max_mm,
                        max_time=max_time.strip(),
                        max_station=max_station.strip()
                    ))
                except (ValueError, AttributeError):
                    continue
        
        return data


# Global singleton
_omirl_adapter = None


def get_omirl_adapter() -> OMIRLAdapter:
    """Get or create the global OMIRL adapter instance."""
    global _omirl_adapter
    if _omirl_adapter is None:
        _omirl_adapter = OMIRLAdapter()
    return _omirl_adapter
