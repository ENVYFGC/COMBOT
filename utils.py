"""
Utility functions and decorators for Combot
Includes improved caching and helper functions
"""

import time
import pickle
import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def async_ttl_cache(seconds: int = 300):
    """
    Async cache decorator with time-to-live and robust key generation
    
    Improvements from original:
    - Uses pickle.dumps for robust key generation
    - Handles unhashable arguments properly
    - Better error handling and logging
    - Automatic cleanup of expired entries
    
    Args:
        seconds: Cache TTL in seconds
    """
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, Any] = {}
        cache_times: Dict[str, float] = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create robust cache key
            try:
                # Use pickle for reliable serialization of complex objects
                key_data = (args, tuple(sorted(kwargs.items())))
                key_bytes = pickle.dumps(key_data)
                # Use hash for consistent string key
                cache_key = hashlib.md5(key_bytes).hexdigest()
            except Exception as e:
                # Fallback to string representation if pickle fails
                logger.warning(f"Cache key generation failed, using fallback: {e}")
                cache_key = f"{str(args)}:{str(sorted(kwargs.items()))}"
            
            now = time.time()
            
            # Check if cached and not expired
            if cache_key in cache and now - cache_times.get(cache_key, 0) < seconds:
                logger.debug(f"Cache hit for {func.__name__}")
                return cache[cache_key]
            
            # Call function and cache result
            try:
                result = await func(*args, **kwargs)
                cache[cache_key] = result
                cache_times[cache_key] = now
                logger.debug(f"Cache miss for {func.__name__}, result cached")
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                raise
            
            # Periodic cleanup of expired entries (every 10 calls)
            if len(cache) > 0 and len(cache) % 10 == 0:
                expired_keys = [
                    k for k, t in cache_times.items() 
                    if now - t >= seconds
                ]
                for k in expired_keys:
                    cache.pop(k, None)
                    cache_times.pop(k, None)
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return result
        
        def clear_cache():
            """Clear all cached entries"""
            cache.clear()
            cache_times.clear()
            logger.info(f"Cache cleared for {func.__name__}")
        
        def cache_info():
            """Get cache statistics"""
            now = time.time()
            expired = sum(1 for t in cache_times.values() if now - t >= seconds)
            return {
                'total': len(cache),
                'expired': expired,
                'active': len(cache) - expired,
                'ttl_seconds': seconds
            }
        
        # Attach utility methods
        wrapper.clear_cache = clear_cache
        wrapper.cache_info = cache_info
        
        return wrapper
    return decorator


def validate_url(url: str) -> bool:
    """
    Validate URL format more robustly
    
    Args:
        url: URL string to validate
        
    Returns:
        True if URL appears valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    if not url:
        return False
    
    # Basic URL pattern validation
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))


def validate_discord_color_hex(color_hex: str) -> Optional[str]:
    """
    Validate and normalize Discord color hex value
    
    Args:
        color_hex: Hex color string
        
    Returns:
        Normalized hex string or None if invalid
    """
    if not color_hex or not isinstance(color_hex, str):
        return None
    
    # Clean the input
    color_hex = color_hex.strip().upper()
    color_hex = color_hex.replace("#", "").replace("0X", "")
    
    # Validate hex format
    import re
    if not re.match(r'^[0-9A-F]{6}$', color_hex):
        return None
    
    return f"0x{color_hex}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to specified length with optional suffix
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    if len(suffix) >= max_length:
        return text[:max_length]
    
    return text[:max_length - len(suffix)] + suffix


def safe_get_nested(data: Dict, keys: list, default: Any = None) -> Any:
    """
    Safely get nested dictionary values
    
    Args:
        data: Dictionary to search
        keys: List of keys for nested access
        default: Default value if key path doesn't exist
        
    Returns:
        Value at key path or default
    """
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError, AttributeError):
        return default


def chunk_list(items: list, chunk_size: int) -> list:
    """
    Split list into chunks of specified size
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")
    
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def format_combo_notation(notation: str) -> str:
    """
    Format combo notation for display
    
    Args:
        notation: Raw combo notation
        
    Returns:
        Formatted notation string
    """
    if not notation:
        return "Unknown Notation"
    
    # Replace common separators with more readable format
    formatted = notation.replace(",", " > ")
    formatted = formatted.replace("->", " > ")
    formatted = formatted.replace("→", " > ")
    
    return formatted.strip()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system usage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    import re
    
    # Remove/replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


class RateLimiter:
    """
    Simple rate limiter for API calls
    """
    
    def __init__(self, max_calls: int, time_window: float):
        """
        Initialize rate limiter
        
        Args:
            max_calls: Maximum calls allowed in time window
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def can_proceed(self) -> bool:
        """
        Check if a call can proceed without hitting rate limit
        
        Returns:
            True if call can proceed, False if rate limited
        """
        now = time.time()
        
        # Remove calls outside the time window
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.time_window]
        
        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def time_until_next_call(self) -> float:
        """
        Get time in seconds until next call is allowed
        
        Returns:
            Seconds until next call is allowed (0 if can call now)
        """
        if self.can_proceed():
            # Remove the call we just added in can_proceed
            self.calls.pop()
            return 0.0
        
        if not self.calls:
            return 0.0
        
        oldest_call = min(self.calls)
        return max(0.0, self.time_window - (time.time() - oldest_call))


def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None):
    """
    Log function calls for debugging
    
    Args:
        func_name: Name of the function
        args: Function arguments
        kwargs: Function keyword arguments
    """
    kwargs = kwargs or {}
    
    # Sanitize arguments for logging (remove sensitive data)
    safe_args = []
    for arg in args:
        if isinstance(arg, str) and len(arg) > 100:
            safe_args.append(f"{arg[:50]}...({len(arg)} chars)")
        else:
            safe_args.append(str(arg))
    
    safe_kwargs = {}
    for k, v in kwargs.items():
        if isinstance(v, str) and len(v) > 100:
            safe_kwargs[k] = f"{v[:50]}...({len(v)} chars)"
        else:
            safe_kwargs[k] = str(v)
    
    logger.debug(f"Called {func_name}({', '.join(safe_args)}, {safe_kwargs})")
