import asyncio
import sys
sys.path.insert(0, 'src')
from rfs.reactive.flux import Flux

async def debug_static():
    # _zip_async_iterators를 직접 호출해서 테스트
    flux1 = Flux.just(1, 2, 3)
    flux2 = Flux.just("a", "b", "c")
    
    print("Static method 직접 호출:")
    async for item1, item2 in Flux._zip_async_iterators(flux1.source(), flux2.source()):
        print(f"  item1={item1}, item2={item2}")

if __name__ == "__main__":
    asyncio.run(debug_static())
