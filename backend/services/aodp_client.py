"""
AODP (Albion Online Data Project) API Client
Handles all communication with the AODP API with rate limiting and caching
"""

import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import hashlib
from urllib.parse import urljoin

class RateLimiter:
    """Simple rate limiter implementation"""
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = datetime.now()
            # Remove old requests outside the time window
            self.requests = [
                req_time for req_time in self.requests
                if now - req_time < timedelta(seconds=self.time_window)
            ]
            
            # Check if we can make a request
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = (oldest_request + timedelta(seconds=self.time_window) - now).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()
            
            # Add current request
            self.requests.append(now)

class AODPClient:
    """Client for Albion Online Data Project API"""
    
    def __init__(self, base_url: str, cache_manager, rate_limit_per_min: int = 120):
        self.base_url = base_url
        self.cache = cache_manager
        self.rate_limiter = RateLimiter(rate_limit_per_min, 60)
        self.client = None
        self.region_urls = {
            "west": "https://west.albion-online-data.com",
            "europe": "https://europe.albion-online-data.com",
            "east": "https://east.albion-online-data.com"
        }
    
    async def initialize(self):
        """Initialize the HTTP client"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate a cache key for the request"""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_region_url(self, region: str) -> str:
        """Get the appropriate URL for the region"""
        return self.region_urls.get(region, self.region_urls["west"])
    
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request with rate limiting and retries"""
        await self.rate_limiter.acquire()
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * (2 ** attempt))
        
        return {}
    
    async def get_prices(
        self,
        region: str,
        items: List[str],
        cities: List[str],
        qualities: List[int] = [0]
    ) -> List[Dict[str, Any]]:
        """
        Get current market prices for items in specified cities
        
        Args:
            region: Server region (west, europe, east)
            items: List of item IDs
            cities: List of city names
            qualities: List of quality levels (0-5)
        
        Returns:
            List of price data dictionaries
        """
        # Build request parameters
        items_str = ",".join(items)
        cities_str = ",".join(cities)
        qualities_str = ",".join(map(str, qualities))
        
        # Check cache
        cache_key = self._get_cache_key(
            f"prices_{region}",
            {"items": items_str, "cities": cities_str, "qualities": qualities_str}
        )
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Build URL
        base_url = self._get_region_url(region)
        url = f"{base_url}/api/v2/stats/prices/{items_str}.json"
        params = {
            "locations": cities_str,
            "qualities": qualities_str
        }
        
        # Make request
        data = await self._make_request(url, params)
        
        # Process and cache the data
        if data:
            self.cache.set(cache_key, data)
        
        return data if isinstance(data, list) else []
    
    async def get_history(
        self,
        region: str,
        item: str,
        city: str,
        timescale: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get historical price data for an item in a specific city
        
        Args:
            region: Server region
            item: Item ID
            city: City name
            timescale: Time scale (1=hourly, 24=daily)
        
        Returns:
            List of historical data points
        """
        # Check cache
        cache_key = self._get_cache_key(
            f"history_{region}",
            {"item": item, "city": city, "timescale": timescale}
        )
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Build URL
        base_url = self._get_region_url(region)
        url = f"{base_url}/api/v2/stats/history/{item}.json"
        params = {
            "locations": city,
            "time-scale": timescale
        }
        
        # Make request
        data = await self._make_request(url, params)
        
        # Process and cache the data
        if data:
            # The response is usually a list with one item per location
            if isinstance(data, list) and len(data) > 0:
                history_data = data[0].get("data", [])
                self.cache.set(cache_key, history_data, ttl=1800)  # Cache for 30 minutes
                return history_data
        
        return []
    
    async def get_item_data(self, item_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get item metadata (names, tiers, etc.)
        Note: This endpoint might not be available in all AODP instances
        """
        # For now, return empty dict as AODP doesn't always provide this
        # In production, you might want to maintain a local database of item metadata
        return {}