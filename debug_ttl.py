import asyncio
import time
from src.rfs.cache.memory_cache import MemoryCache, MemoryCacheConfig

async def debug_ttl_zero():
    config = MemoryCacheConfig(
        max_size=100,
        eviction_policy="lru",
        cleanup_interval=1,
        lazy_expiration=True,
        min_ttl=1,
    )
    cache = MemoryCache(config)
    await cache.connect()
    
    # TTL=0으로 설정 
    result = await cache.set("zero_ttl", "value", ttl=0)
    print(f"Set result: {result}")
    
    # 캐시 내부 상태 확인
    cache_key = cache._make_key("zero_ttl")
    if cache_key in cache._data:
        item = cache._data[cache_key]
        print(f"created_at: {item.created_at}")
        print(f"expires_at: {item.expires_at}")
        print(f"is_expired(): {item.is_expired()}")
        print(f"current_time: {time.time()}")
    
    # 즉시 조회
    result = await cache.get("zero_ttl")
    print(f"Get result: {result}")
    print(f"Get value: {result.get() if result.is_success() else 'None'}")
    
    await cache.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_ttl_zero())
