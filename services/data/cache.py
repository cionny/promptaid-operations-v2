# services/data/cache.py
"""
TTL Cache Service - File-Based Caching for Web Scraping

This module provides a simple, file-based caching system with TTL (time-to-live)
functionality to reduce load on websites and improve response times for
web scraping operations.

Purpose:
- Cache expensive web scraping operations with configurable TTL
- Reduce load on OMIRL and other websites (respectful scraping)
- Improve tool response times for repeated queries
- Handle cache invalidation and cleanup
- Store both scraped data and metadata

Implementation:
- File-based storage in data/cache/ directory
- JSON serialization for simple data structures
- Atomic writes to prevent corruption
- Automatic cleanup of expired entries
- Cache key generation from tool + task + optional params

Called by:
- tools/omirl/: Caches OMIRL scraping results
- Future: Any tool needing to cache web scraping operations

Dependencies:
- None from other services/* modules (independent utility)
- Standard library only (os, time, json, hashlib, pathlib)

Main Function:
    get_cached(tool, task, data_fn, ttl, **params) -> Any
    
Cache Strategy:
- Default 15-minute TTL for live data (emergency management needs freshness)
- Longer TTL for static reference data
- Cache invalidation on scraping errors
- Separate cache for screenshots/artifacts

Web Scraping Considerations:
- Cache key includes tool, task, and optional parameters
- Invalidate cache if website structure changes detected
- Store scraping metadata (timestamp, source URL, warnings)
- Balance freshness needs vs. website load reduction
"""

import json
import hashlib
import time
import asyncio
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from datetime import datetime


class CacheService:
    """
    Simple file-based caching service with TTL support.
    
    Thread-safe for single-process use. For multi-process scenarios,
    consider file locking or a proper cache like Redis.
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Initialize cache service.
        
        Args:
            cache_dir: Directory to store cache files (relative to project root)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_cache_key(self, tool: str, task: str, **params) -> str:
        """
        Generate a unique cache key from tool, task, and parameters.
        
        Args:
            tool: Tool name (e.g., "omirl")
            task: Task name (e.g., "livelli_idrometrici")
            **params: Optional parameters to include in cache key
        
        Returns:
            Hex string cache key
        """
        # Create a deterministic string from inputs
        key_parts = [tool, task]
        
        # Add sorted params for deterministic key
        if params:
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}={v}" for k, v in sorted_params])
        
        key_string = "|".join(key_parts)
        
        # Hash for filesystem-safe key
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def get_cached(
        self,
        tool: str,
        task: str,
        data_fn: Callable[[], Any],
        ttl: int = 900,  # 15 minutes default
        **params
    ) -> Dict[str, Any]:
        """
        Get cached data or fetch fresh data if cache is expired/missing.
        
        Args:
            tool: Tool name (e.g., "omirl")
            task: Task name (e.g., "livelli_idrometrici")
            data_fn: Function to call if cache miss (must return dict-serializable data)
            ttl: Time-to-live in seconds (default: 900 = 15 minutes)
            **params: Optional parameters for cache key differentiation
        
        Returns:
            Dict with keys:
                - 'data': The cached or freshly fetched data
                - 'metadata': Cache metadata (timestamp, ttl, cache_hit, etc.)
        """
        cache_key = self._generate_cache_key(tool, task, **params)
        cache_path = self._get_cache_path(cache_key)
        
        # Try to load from cache
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_entry = json.load(f)
                
                # Check if cache is still valid
                cached_time = cached_entry['metadata']['timestamp']
                age = time.time() - cached_time
                
                if age < ttl:
                    # Cache hit!
                    cached_entry['metadata']['cache_hit'] = True
                    cached_entry['metadata']['cache_age_seconds'] = int(age)
                    cached_entry['metadata']['cache_age_human'] = self._format_age(age)
                    return cached_entry
                else:
                    # Cache expired
                    cached_entry['metadata']['cache_expired'] = True
                    
            except (json.JSONDecodeError, KeyError, IOError) as e:
                # Cache file corrupted or invalid, will refetch
                print(f"⚠️  Cache read error: {e}")
        
        # Cache miss or expired - fetch fresh data
        print(f"🔄 Cache miss for {tool}/{task}, fetching fresh data...")
        
        try:
            fresh_data = data_fn()
            
            # Prepare cache entry
            cache_entry = {
                'data': fresh_data,
                'metadata': {
                    'tool': tool,
                    'task': task,
                    'params': params,
                    'timestamp': time.time(),
                    'datetime': datetime.now().isoformat(),
                    'ttl': ttl,
                    'cache_hit': False,
                    'cache_key': cache_key
                }
            }
            
            # Write to cache atomically
            self._write_cache(cache_path, cache_entry)
            
            return cache_entry
            
        except Exception as e:
            # If fetching fails, return error info
            print(f"❌ Error fetching fresh data: {e}")
            raise
    
    async def get_cached_async(
        self,
        tool: str,
        task: str,
        data_fn: Callable,
        ttl: int = 900,  # 15 minutes default
        **params
    ) -> Dict[str, Any]:
        """
        Get cached data or fetch fresh data if cache is expired/missing (async version).
        
        This version supports async data_fn functions. If data_fn is sync, it will
        still work but run in the current thread.
        
        Args:
            tool: Tool name (e.g., "omirl")
            task: Task name (e.g., "livelli_idrometrici")
            data_fn: Function to call if cache miss (async or sync, must return dict-serializable data)
            ttl: Time-to-live in seconds (default: 900 = 15 minutes)
            **params: Optional parameters for cache key differentiation
        
        Returns:
            Dict with keys:
                - 'data': The cached or freshly fetched data
                - 'metadata': Cache metadata (timestamp, ttl, cache_hit, etc.)
        """
        cache_key = self._generate_cache_key(tool, task, **params)
        cache_path = self._get_cache_path(cache_key)
        
        # Try to load from cache (same as sync version)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_entry = json.load(f)
                
                # Check if cache is still valid
                cached_time = cached_entry['metadata']['timestamp']
                age = time.time() - cached_time
                
                if age < ttl:
                    # Cache hit!
                    cached_entry['metadata']['cache_hit'] = True
                    cached_entry['metadata']['cache_age_seconds'] = int(age)
                    cached_entry['metadata']['cache_age_human'] = self._format_age(age)
                    return cached_entry
                else:
                    # Cache expired
                    cached_entry['metadata']['cache_expired'] = True
                    
            except (json.JSONDecodeError, KeyError, IOError) as e:
                # Cache file corrupted or invalid, will refetch
                print(f"⚠️  Cache read error: {e}")
        
        # Cache miss or expired - fetch fresh data
        print(f"🔄 Cache miss for {tool}/{task}, fetching fresh data...")
        
        try:
            # Call data_fn to get result or coroutine
            result = data_fn()
            
            # Check if result is a coroutine (not just if data_fn is async)
            if inspect.iscoroutine(result):
                fresh_data = await result
            else:
                fresh_data = result
            
            # Prepare cache entry
            cache_entry = {
                'data': fresh_data,
                'metadata': {
                    'tool': tool,
                    'task': task,
                    'params': params,
                    'timestamp': time.time(),
                    'datetime': datetime.now().isoformat(),
                    'ttl': ttl,
                    'cache_hit': False,
                    'cache_key': cache_key
                }
            }
            
            # Write to cache atomically
            self._write_cache(cache_path, cache_entry)
            
            return cache_entry
            
        except Exception as e:
            # If fetching fails, return error info
            print(f"❌ Error fetching fresh data: {e}")
            raise
    
    def _write_cache(self, cache_path: Path, cache_entry: Dict[str, Any]):
        """
        Write cache entry to file atomically.
        
        Uses temp file + rename for atomic write to prevent corruption.
        """
        temp_path = cache_path.with_suffix('.tmp')
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_path.replace(cache_path)
            print(f"✅ Cache written: {cache_path.name}")
            
        except Exception as e:
            print(f"❌ Cache write error: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def invalidate(self, tool: str, task: str, **params):
        """
        Invalidate (delete) a specific cache entry.
        
        Args:
            tool: Tool name
            task: Task name
            **params: Parameters used in cache key
        """
        cache_key = self._generate_cache_key(tool, task, **params)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            cache_path.unlink()
            print(f"🗑️  Cache invalidated: {tool}/{task}")
            return True
        return False
    
    def cleanup_expired(self, max_age_hours: int = 24):
        """
        Remove all cache files older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours before deletion
        """
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        removed_count = 0
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                
                age = current_time - entry['metadata']['timestamp']
                
                if age > max_age_seconds:
                    cache_file.unlink()
                    removed_count += 1
                    
            except (json.JSONDecodeError, KeyError, IOError):
                # Corrupted file, remove it
                cache_file.unlink()
                removed_count += 1
        
        if removed_count > 0:
            print(f"🧹 Cleaned up {removed_count} expired cache entries")
        
        return removed_count
    
    def clear_all(self, tool: Optional[str] = None, task: Optional[str] = None):
        """
        Clear all cache or filter by tool/task.
        
        Args:
            tool: If provided, only clear caches for this tool
            task: If provided (with tool), only clear caches for this task
        """
        removed_count = 0
        
        for cache_file in self.cache_dir.glob("*.json"):
            should_remove = True
            
            if tool or task:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        entry = json.load(f)
                    
                    metadata = entry.get('metadata', {})
                    
                    if tool and metadata.get('tool') != tool:
                        should_remove = False
                    
                    if task and metadata.get('task') != task:
                        should_remove = False
                        
                except (json.JSONDecodeError, KeyError, IOError):
                    # Corrupted file, remove anyway
                    pass
            
            if should_remove:
                cache_file.unlink()
                removed_count += 1
        
        filter_msg = f" for {tool}/{task}" if tool or task else ""
        print(f"🗑️  Cleared {removed_count} cache entries{filter_msg}")
        
        return removed_count
    
    @staticmethod
    def _format_age(seconds: float) -> str:
        """Format age in seconds to human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


# Global cache instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service