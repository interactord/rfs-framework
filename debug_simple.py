import asyncio
import sys
sys.path.insert(0, 'src')
from rfs.reactive.flux import Flux

async def debug():
    # 간단한 디버깅
    flux1 = Flux.just(1, 2, 3)
    flux2 = Flux.just("a", "b", "c")
    
    print("flux1 단독:")
    result1 = await flux1.collect_list()
    print(f"  {result1}")
    
    print("flux2 단독:")
    flux2_new = Flux.just("a", "b", "c")  
    result2 = await flux2_new.collect_list()
    print(f"  {result2}")
    
    print("zip 테스트:")
    flux1_new = Flux.just(1, 2, 3)
    flux2_new = Flux.just("a", "b", "c")
    zipped = flux1_new.zip(flux2_new)
    
    # 직접 이터레이트해서 확인
    print("  zip 직접 이터레이션:")
    async for item in zipped.source():
        print(f"    {item}")
    
    # collect_list로 확인
    flux1_final = Flux.just(1, 2, 3)
    flux2_final = Flux.just("a", "b", "c") 
    result = await flux1_final.zip(flux2_final).collect_list()
    print(f"  최종 결과: {result}")

if __name__ == "__main__":
    asyncio.run(debug())
