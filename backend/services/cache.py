"""
Cache manager for storing API responses
Simple in-memory implementation with TTL support
"""

import time
from typing import Any, Optional, Dict
from threading import Lock

class CacheManager:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if time.time() < entry["expires_at"]:
                    return entry["value"]
                else:
                    # Remove expired entry
                    del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.ttl_seconds
        with self.lock:
            self.cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl
            }
    
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """Get number of cached entries"""
        with self.lock:
            # Clean expired entries first
            current_time = time.time()
            expired_keys = [
                key for key, entry in self.cache.items()
                if current_time >= entry["expires_at"]
            ]
            for key in expired_keys:
                del self.cache[key]
            
            return len(self.cache)
    
    def cleanup_expired(self) -> None:
        """Remove all expired entries"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self.cache.items()
                if current_time >= entry["expires_at"]
            ]
            for key in expired_keys:
                del self.cache[key]


class RedisCache:
    """
    Redis cache implementation (optional, for production)
    Requires redis package: pip install redis
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl_seconds: int = 600):
        try:
            import redis
            self.redis_client = redis.from_url(redis_url)
            self.ttl_seconds = ttl_seconds
            self.enabled = True
        except ImportError:
            print("Redis not installed. Using in-memory cache instead.")
            self.enabled = False
            self.fallback = CacheManager(ttl_seconds)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.enabled:
            return self.fallback.get(key)
        
        try:
            import json
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"Redis get error: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in Redis cache with TTL"""
        if not self.enabled:
            return self.fallback.set(key, value, ttl)
        
        try:
            import json
            ttl = ttl or self.ttl_seconds
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
        except Exception as e:
            print(f"Redis set error: {e}")
    
    def delete(self, key: str) -> None:
        """Delete key from Redis cache"""
        if not self.enabled:
            return self.fallback.delete(key)
        
        try:
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Redis delete error: {e}")
    
    def clear(self) -> None:
        """Clear all cache entries"""
        if not self.enabled:
            return self.fallback.clear()
        
        try:
            self.redis_client.flushdb()
        except Exception as e:
            print(f"Redis clear error: {e}")
    
    def size(self) -> int:
        """Get number of cached entries"""
        if not self.enabled:
            return self.fallback.size()
        
        try:
            return self.redis_client.dbsize()
        except Exception as e:
            print(f"Redis size error: {e}")
            return 0