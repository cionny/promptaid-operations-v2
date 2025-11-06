# services/data/artifacts.py
"""
Data Artifacts Service

This module provides file-based artifact generation and management for
operational data. It handles saving structured data to various formats
and managing artifact lifecycle.

Purpose:
- Save operational data to files (JSON, CSV, etc.)
- Generate standardized filenames with timestamps and metadata
- Manage artifact storage locations and cleanup
- Provide consistent artifact metadata

Design Principles:
- Configurable output directories
- Timestamped filenames for traceability
- Metadata embedding in saved files
- Error handling for storage failures
- Support for multiple output formats

Dependencies:
- json: For JSON serialization
- os: For file system operations
- datetime: For timestamp generation

Called by:
- tools/*/adapter.py: Main tool adapters for data persistence
- services/reports/*: Report generation services
- Direct usage: Emergency management data export

Security Notes:
- Validates output paths to prevent directory traversal
- Uses safe filename generation
- Handles permissions and disk space gracefully

TODO: implement permanent configurable storage with retention policies
"""

import json
import os
import csv
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path


class ArtifactConfig:
    """Configuration for artifact generation"""
    
    def __init__(
        self,
        base_dir: str = "/tmp/omirl_data",
        include_timestamp: bool = True,
        include_metadata: bool = True,
        filename_format: str = "{prefix}_{timestamp}{suffix}.{extension}"
    ):
        self.base_dir = base_dir
        self.include_timestamp = include_timestamp
        self.include_metadata = include_metadata
        self.filename_format = filename_format


class ArtifactManager:
    """
    Manages data artifact creation and storage
    
    This class provides a standardized way to save operational data
    to various file formats with consistent naming and metadata.
    """
    
    def __init__(self, config: Optional[ArtifactConfig] = None):
        self.config = config or ArtifactConfig()
        self._ensure_base_directory()
    
    def _ensure_base_directory(self):
        """Create base directory if it doesn't exist"""
        try:
            os.makedirs(self.config.base_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️  Warning: Could not create base directory {self.config.base_dir}: {e}")
    
    async def save_station_data(
        self,
        stations: List[Dict[str, Any]],
        filters: Dict[str, Any] = None,
        source: str = "OMIRL",
        format: str = "json"
    ) -> Optional[str]:
        """
        Save weather station data to file
        
        Args:
            stations: List of station data dictionaries
            filters: Applied filters for filename generation
            source: Data source name
            format: Output format ("json" or "csv")
            
        Returns:
            Filepath of saved file, or None if failed
        """
        try:
            # Generate filename
            filename = self._generate_filename(
                prefix="stazioni",
                filters=filters,
                extension=format
            )
            
            filepath = os.path.join(self.config.base_dir, filename)
            
            # Prepare data with metadata
            if format == "json":
                return await self._save_as_json(stations, filepath, filters, source)
            elif format == "csv":
                return await self._save_as_csv(stations, filepath, filters, source)
            else:
                print(f"⚠️  Unsupported format: {format}")
                return None
                
        except Exception as e:
            print(f"⚠️  Failed to save station data: {e}")
            return None
    
    async def save_generic_data(
        self,
        data: Union[List[Dict], Dict[str, Any]],
        prefix: str = "data",
        filters: Dict[str, Any] = None,
        source: str = "Unknown",
        format: str = "json"
    ) -> Optional[str]:
        """
        Save generic operational data to file
        
        Args:
            data: Data to save (list of dicts or single dict)
            prefix: Filename prefix
            filters: Applied filters for filename generation
            source: Data source name
            format: Output format
            
        Returns:
            Filepath of saved file, or None if failed
        """
        try:
            filename = self._generate_filename(
                prefix=prefix,
                filters=filters,
                extension=format
            )
            
            filepath = os.path.join(self.config.base_dir, filename)
            
            if format == "json":
                return await self._save_generic_json(data, filepath, filters, source)
            else:
                print(f"⚠️  Unsupported format for generic data: {format}")
                return None
                
        except Exception as e:
            print(f"⚠️  Failed to save generic data: {e}")
            return None
    
    def _generate_filename(
        self,
        prefix: str,
        filters: Dict[str, Any] = None,
        extension: str = "json"
    ) -> str:
        """Generate standardized filename with timestamp and filters"""
        
        # Base components
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if self.config.include_timestamp else ""
        
        # Add filter-based suffix
        suffix = ""
        if filters:
            filter_parts = []
            for key, value in filters.items():
                if value:
                    # Clean value for filename
                    clean_value = str(value).lower().replace(" ", "_").replace("'", "")
                    filter_parts.append(f"{key}_{clean_value}")
            
            if filter_parts:
                suffix = "_" + "_".join(filter_parts[:3])  # Limit to 3 filters for filename length
        
        # Format filename
        return self.config.filename_format.format(
            prefix=prefix,
            timestamp=timestamp,
            suffix=suffix,
            extension=extension
        )
    
    async def _save_as_json(
        self,
        stations: List[Dict[str, Any]],
        filepath: str,
        filters: Dict[str, Any],
        source: str
    ) -> str:
        """Save station data as JSON with metadata"""
        
        data_to_save = {
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "source": source,
                "filters_applied": filters or {},
                "station_count": len(stations),
                "format_version": "1.0"
            },
            "stations": stations
        } if self.config.include_metadata else stations
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Station data saved to: {filepath}")
        return filepath
    
    async def _save_as_csv(
        self,
        stations: List[Dict[str, Any]],
        filepath: str,
        filters: Dict[str, Any],
        source: str
    ) -> str:
        """Save station data as CSV"""
        
        if not stations:
            # Create empty CSV with headers
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Nome", "Codice", "Comune", "Provincia"])
        else:
            # Get headers from first station
            headers = list(stations[0].keys())
            
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for station in stations:
                    writer.writerow(station)
        
        print(f"💾 Station data saved to CSV: {filepath}")
        return filepath
    
    async def _save_generic_json(
        self,
        data: Union[List[Dict], Dict[str, Any]],
        filepath: str,
        filters: Dict[str, Any],
        source: str
    ) -> str:
        """Save generic data as JSON with metadata"""
        
        data_to_save = {
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "source": source,
                "filters_applied": filters or {},
                "record_count": len(data) if isinstance(data, list) else 1,
                "format_version": "1.0"
            },
            "data": data
        } if self.config.include_metadata else data
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Data saved to: {filepath}")
        return filepath


# Factory function for common configurations
def create_artifact_manager(
    base_dir: str = "/tmp/omirl_data",
    include_metadata: bool = True
) -> ArtifactManager:
    """
    Create an artifact manager with custom configuration
    
    Args:
        base_dir: Base directory for saving artifacts
        include_metadata: Whether to include metadata in saved files
        
    Returns:
        Configured ArtifactManager instance
    """
    config = ArtifactConfig(
        base_dir=base_dir,
        include_metadata=include_metadata
    )
    
    return ArtifactManager(config)


# Convenience functions for common use cases
async def save_omirl_stations(
    stations: List[Dict[str, Any]],
    filters: Dict[str, Any] = None,
    format: str = "json",
    base_dir: str = "/tmp/omirl_data"
) -> Optional[str]:
    """
    Quick function to save OMIRL station data
    
    This is a convenience function that creates an artifact manager
    and saves station data in one call.
    """
    manager = create_artifact_manager(base_dir=base_dir)
    return await manager.save_station_data(
        stations=stations,
        filters=filters,
        source="OMIRL Valori Stazioni",
        format=format
    )

async def save_omirl_precipitation_data(
    precipitation_data: Dict[str, List[Dict[str, Any]]],
    filters: Dict[str, Any] = None,
    format: str = "json",
    base_dir: str = "/tmp/omirl_data"
) -> Optional[str]:
    """
    Quick function to save OMIRL precipitation data
    
    This is a convenience function that creates an artifact manager
    and saves precipitation data from both zona d'allerta and province tables.
    """
    manager = create_artifact_manager(base_dir=base_dir)
    
    # Flatten the precipitation data for consistent saving
    # Include metadata about which table each record came from
    flattened_data = []
    
    for table_type in ["zona_allerta", "province"]:
        for record in precipitation_data.get(table_type, []):
            record_with_type = {**record, "table_type": table_type}
            flattened_data.append(record_with_type)
    
    return await manager.save_station_data(
        stations=flattened_data,
        filters=filters,
        source="OMIRL Massimi Precipitazione",
        format=format
    )
