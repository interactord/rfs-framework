import asyncio
import sys
sys.path.insert(0, 'src')
from rfs.reactive.flux import Flux

async def debug_methods():
    flux1 = Flux.just(1, 2, 3)
    flux2 = Flux.just("a", "b", "c")
    
    print("zip_with 직접 호출:")
    result_zip_with = await flux1.zip_with(flux2).collect_list()
    print(f"  {result_zip_with}")
    
    print("zip 메서드 호출:")
    flux1_new = Flux.just(1, 2, 3)
    flux2_new = Flux.just("a", "b", "c")
    result_zip = await flux1_new.zip(flux2_new).collect_list()
    print(f"  {result_zip}")

if __name__ == "__main__":
    asyncio.run(debug_methods())
