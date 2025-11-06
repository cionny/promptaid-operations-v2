"""
OMIRL Adapter for operations-v2

Minimal adapter that delegates to the LivelliIdrometriciTask from operations repo.
This is a service layer - tools call this, not the scraper directly.
"""

from typing import Dict, Any, List


class OMIRLAdapter:
    """Minimal OMIRL adapter for v2 - delegates to operations scraper."""
    
    def fetch_livelli_idrometrici(self) -> List[Dict[str, Any]]:
        """
        Fetch hydrometric levels from OMIRL.
        
        Returns:
            List of station dictionaries with levels and metadata
        """
        from tools.omirl.tables.livelli_idro import LivelliIdrometriciTask
        
        task = LivelliIdrometriciTask()
        return task.scrape_all_zones()


# Global singleton
_omirl_adapter = None


def get_omirl_adapter() -> OMIRLAdapter:
    """Get or create the global OMIRL adapter instance."""
    global _omirl_adapter
    if _omirl_adapter is None:
        _omirl_adapter = OMIRLAdapter()
    return _omirl_adapter
        
    async def fetch_data(
        self, 
        data_type: str, 
        filters: Dict[str, Any] = None,
        use_cache: bool = True,
        cache_ttl: int = 900  # 15 minutes default
    ) -> Dict[str, Any]:
        """Fetch data of a specific type with optional filters and caching
        
        This is the SINGLE point where caching is applied for ALL OMIRL tasks.
        All raw scraping happens in _fetch_* methods, caching happens here.
        """
        filters = filters or {}
        
        try:
            if data_type == "valori_stazioni":
                if use_cache:
                    # For valori_stazioni, only sensor_type affects scraping
                    # comune and provincia are Python post-filters, not cache keys
                    cache_params = {}
                    if "sensor_type" in filters:
                        cache_params["sensor_type"] = filters["sensor_type"]
                    
                    cache_result = await self.cache_service.get_cached_async(
                        tool="omirl",
                        task="valori_stazioni",
                        data_fn=lambda: self._fetch_valori_stazioni(filters),
                        ttl=cache_ttl,
                        **cache_params
                    )
                    
                    # Cache service returns {data: ..., metadata: ...}
                    # Extract the actual adapter result from cache
                    return cache_result.get('data', cache_result)
                else:
                    return await self._fetch_valori_stazioni(filters)
            elif data_type == "massimi_precipitazioni":
                if use_cache:
                    # For massimi_precipitazioni, cache everything together
                    # No pre-scraping filters, all filtering is post-scraping
                    cache_result = await self.cache_service.get_cached_async(
                        tool="omirl",
                        task="massimi_precipitazioni",
                        data_fn=lambda: self._fetch_massimi_precipitazioni(filters),
                        ttl=cache_ttl
                        # No filter params in cache key - everything cached together
                    )
                    
                    # Cache service returns {data: ..., metadata: ...}
                    # Extract the actual adapter result from cache
                    return cache_result.get('data', cache_result)
                else:
                    return await self._fetch_massimi_precipitazioni(filters)
            elif data_type == "livelli_idrometrici":
                if use_cache:
                    # For livelli_idrometrici, cache everything together
                    # All filtering is post-scraping
                    cache_result = await self.cache_service.get_cached_async(
                        tool="omirl",
                        task="livelli_idrometrici",
                        data_fn=lambda: self._fetch_livelli_idrometrici(filters),
                        ttl=cache_ttl
                        # No filter params in cache key - everything cached together
                    )
                    
                    # Cache service returns {data: ..., metadata: ...}
                    # Extract the actual adapter result from cache
                    return cache_result.get('data', cache_result)
                else:
                    return await self._fetch_livelli_idrometrici(filters)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "message": f"Failed to fetch {data_type}: {e}"
            }
    
    def get_supported_data_types(self) -> List[str]:
        """Get list of supported data types"""
        return ["valori_stazioni", "massimi_precipitazioni"]
    
    def validate_filters(
        self, 
        data_type: str, 
        filters: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate filters for a data type"""
        errors = []
        corrected_filters = filters.copy()
        
        if data_type == "valori_stazioni":
            # Validate sensor type
            sensor_type = filters.get("sensor_type")
            if sensor_type and sensor_type not in self.knowledge.SENSOR_NAME_TO_INDEX:
                errors.append(f"Invalid sensor type: {sensor_type}")
                
        elif data_type == "massimi_precipitazioni":
            # Note: Geographic validation is now handled by the validator from geography.yaml
            # This is a placeholder for backward compatibility
            pass
                
        return len(errors) == 0, corrected_filters, errors
    
    async def _fetch_valori_stazioni(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch weather station data using OMIRL configuration"""
        context = None
        page = None
        
        try:
            print("🌊 Starting OMIRL valori stazioni extraction...")
            print(f"🔍 DEBUG: Filters received: {filters}")
            
            # Get browser context
            context = await self.browser_manager.get_context("omirl_valori_stazioni")
            page = await context.new_page()
            
            # Navigate to sensorstable page
            valori_url = self.site_config.base_url + self.site_config.urls["valori_stazioni"]
            success = await self.browser_manager.navigate_with_retry(page, valori_url)
            if not success:
                raise NavigationError("Failed to navigate to OMIRL sensorstable page")
            
            # Apply sensor type filter if specified
            sensor_type = filters.get("sensor_type")
            if sensor_type:
                await self._apply_sensor_filter(page, sensor_type)
            
            # Wait for AngularJS using OMIRL timing configuration
            timing = self.site_config.data_mappings["timing"]
            await page.wait_for_timeout(timing["post_navigation_wait"])
            
            try:
                await page.wait_for_load_state('networkidle', timeout=timing["network_idle_timeout"])
                print("🌐 Network activity settled")
            except:
                print("⚠️  Network wait timeout - proceeding anyway")
            
            # Additional wait for Angular rendering
            await page.wait_for_timeout(timing["table_load_wait"])
            
            # Extract table data using generic scraper with OMIRL configuration
            table_config = create_omirl_table_config("valori_stazioni")
            stations_data = await self.table_scraper.extract_table_data(page, table_config)
            
            print(f"🔍 DEBUG: Extracted {len(stations_data)} raw station records")
            if len(stations_data) > 0:
                print(f"🔍 DEBUG: First record sample: {stations_data[0]}")
            else:
                print("⚠️ DEBUG: NO DATA extracted from table!")
            
            # Apply post-processing filters
            filtered_data = self._apply_post_filters(stations_data, filters)
            
            print(f"🔍 DEBUG: After filtering: {len(filtered_data)} records")
            if len(filtered_data) == 0 and len(stations_data) > 0:
                print(f"⚠️ DEBUG: Filtering removed all data!")
                print(f"⚠️ DEBUG: Filters applied: {filters}")
            
            # Apply rate limiting
            await self.browser_manager.apply_rate_limiting()
            
            return {
                "success": True,
                "data": filtered_data,
                "message": f"Successfully extracted {len(filtered_data)} station records",
                "metadata": {
                    "total_stations_found": len(stations_data),
                    "stations_after_filtering": len(filtered_data),
                    "sensor_type_requested": sensor_type,
                    "extraction_method": "Generic scraper with OMIRL config",
                    "source_url": valori_url
                }
            }
            
        finally:
            if page:
                await page.close()
    
    async def _fetch_massimi_precipitazioni(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch maximum precipitation data using OMIRL configuration"""
        context = None
        page = None
        
        try:
            print("🌧️ Starting OMIRL massimi precipitazioni extraction...")
            
            # Get browser context
            context = await self.browser_manager.get_context("omirl_precipitazioni")
            page = await context.new_page()
            
            # Navigate to maxtable page
            maxtable_url = self.site_config.base_url + self.site_config.urls["massimi_precipitazione"]
            success = await self.browser_manager.navigate_with_retry(page, maxtable_url)
            if not success:
                raise NavigationError("Failed to navigate to OMIRL maxtable page")
            
            # Wait for AngularJS
            timing = self.site_config.data_mappings["timing"]
            await page.wait_for_timeout(timing["post_navigation_wait"])
            
            try:
                await page.wait_for_load_state('networkidle', timeout=timing["network_idle_timeout"])
                print("🌐 Network activity settled")
            except:
                print("⚠️  Network wait timeout - proceeding anyway")
            
            await page.wait_for_timeout(timing["table_load_wait"])
            
            # Extract both tables using generic scraper
            zona_config = create_omirl_table_config("massimi_precipitazioni_zona")
            province_config = create_omirl_table_config("massimi_precipitazioni_province")
            
            zona_allerta_data = await self.table_scraper.extract_table_by_index(page, 4, zona_config)
            province_data = await self.table_scraper.extract_table_by_index(page, 5, province_config)
            
            # Apply rate limiting
            await self.browser_manager.apply_rate_limiting()
            
            result_data = {
                "zona_allerta": zona_allerta_data,
                "province": province_data
            }
            
            # Apply filters
            filtered_data = self._apply_precipitation_filters(result_data, filters)
            
            return {
                "success": True,
                "data": filtered_data,
                "message": f"Successfully extracted precipitation data",
                "metadata": {
                    "zona_allerta_records": len(filtered_data.get("zona_allerta", [])),
                    "province_records": len(filtered_data.get("province", [])),
                    "extraction_method": "Generic scraper with OMIRL config",
                    "source_url": maxtable_url
                }
            }
            
        finally:
            if page:
                await page.close()
    
    async def _apply_sensor_filter(self, page: Page, sensor_type: Union[str, int]) -> None:
        """Apply sensor type filter using OMIRL configuration"""
        try:
            # Convert sensor_type to index using OMIRL knowledge
            sensor_mapping = self.site_config.data_mappings["sensor_name_to_index"]
            
            if isinstance(sensor_type, str):
                if sensor_type in sensor_mapping:
                    filter_index = sensor_mapping[sensor_type]
                else:
                    print(f"⚠️  Unknown sensor type '{sensor_type}', skipping filter")
                    return
            else:
                filter_index = sensor_type
            
            # Validate index using OMIRL knowledge
            sensor_types = self.site_config.data_mappings["sensor_types"]
            if filter_index not in sensor_types:
                print(f"⚠️  Invalid sensor type index {filter_index}, skipping filter")
                return
            
            print(f"🔧 Applying sensor filter: {sensor_types[filter_index]} (index {filter_index})")
            
            # Use OMIRL selector
            filter_selector = self.site_config.selectors["sensor_type_filter"]
            await page.wait_for_selector(filter_selector, timeout=8000)
            await page.select_option(filter_selector, value=str(filter_index))
            
            # Wait for AngularJS using OMIRL timing
            timing = self.site_config.data_mappings["timing"]
            await page.wait_for_timeout(timing["filter_apply_wait"])
            
            print("✅ Sensor filter applied successfully")
            
        except Exception as e:
            print(f"⚠️  Failed to apply sensor filter: {e}")
    
    def _apply_post_filters(self, data: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply post-processing filters to station data"""
        filtered_data = data.copy()
        
        # Apply provincia filter
        provincia = filters.get("provincia")
        if provincia:
            filtered_data = [
                station for station in filtered_data 
                if station.get("Provincia", "").upper() == provincia.upper()
            ]
        
        # Apply comune filter
        comune = filters.get("comune")
        if comune:
            filtered_data = [
                station for station in filtered_data 
                if station.get("Comune", "").upper() == comune.upper()
            ]
        
        return filtered_data
    
    def _apply_precipitation_filters(
        self, 
        data: Dict[str, List[Dict]], 
        filters: Dict[str, Any]
    ) -> Dict[str, List[Dict]]:
        """Apply filters to precipitation data"""
        filtered_data = {"zona_allerta": [], "province": []}
        
        # Filter zona d'allerta data
        zona_filter = filters.get("zona_allerta") or filters.get("zona")
        if zona_filter:
            filtered_data["zona_allerta"] = [
                record for record in data.get("zona_allerta", [])
                if zona_filter.upper() in str(record).upper()
            ]
        else:
            filtered_data["zona_allerta"] = data.get("zona_allerta", [])
        
        # Filter province data
        provincia_filter = filters.get("provincia")
        if provincia_filter:
            filtered_data["province"] = [
                record for record in data.get("province", [])
                if provincia_filter.upper() in str(record).upper()
            ]
        else:
            filtered_data["province"] = data.get("province", [])
        
        return filtered_data
    
    async def _fetch_livelli_idrometrici(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch livelli idrometrici data - PURE SCRAPING, NO CACHING
        
        This method is called by fetch_data() which handles caching at the adapter level.
        This ensures consistent caching behavior across all OMIRL tasks.
        
        Returns:
            List of station dictionaries (raw scraped data)
        """
        # Use LivelliIdrometriciTask from operations repo
        # This is temporary - we'll port the scraper to v2 later
        from tools.omirl.tables.livelli_idro import LivelliIdrometriciTask
        
        task = LivelliIdrometriciTask()
        data = task.scrape_all_zones()
        return data
    
    def fetch_livelli_idrometrici(self) -> List[Dict[str, Any]]:
        """
        Public synchronous method to fetch livelli idrometrici.
        Used by tools that need raw OMIRL data without caching.
        
        Returns:
            List of station dictionaries (raw scraped data)
        """
        from tools.omirl.tables.livelli_idro import LivelliIdrometriciTask
        
        task = LivelliIdrometriciTask()
        return task.scrape_all_zones()
    
    async def cleanup(self):
        """Cleanup browser resources"""
        await self.browser_manager.close_all()


# Factory function for easy instantiation
def create_omirl_adapter() -> OMIRLAdapter:
    """Factory function to create an OMIRL adapter"""
    return OMIRLAdapter()


# Global singleton
_omirl_adapter = None


def get_omirl_adapter() -> OMIRLAdapter:
    """Get or create the global OMIRL adapter instance."""
    global _omirl_adapter
    if _omirl_adapter is None:
        _omirl_adapter = OMIRLAdapter()
    return _omirl_adapter
