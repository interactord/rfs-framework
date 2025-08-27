import asyncio
from src.rfs.reactive.flux import Flux

async def debug_zip():
    print("=== Flux ZIP 디버깅 ===")
    
    # 테스트 데이터
    flux1 = Flux.just(1, 2, 3)
    flux2 = Flux.just("a", "b", "c")
    
    print("flux1 데이터:")
    async for item in flux1.source():
        print(f"  {item}")
    
    print("flux2 데이터:")
    flux2_new = Flux.just("a", "b", "c")  # 새로운 인스턴스 생성
    async for item in flux2_new.source():
        print(f"  {item}")
    
    # ZIP 테스트
    flux1_new = Flux.just(1, 2, 3)
    flux2_new = Flux.just("a", "b", "c")
    print("ZIP 결과:")
    zipped = flux1_new.zip(flux2_new)
    result = await zipped.collect_list()
    print(f"  결과: {result}")
    print(f"  예상: [(1, 'a'), (2, 'b'), (3, 'c')]")

if __name__ == "__main__":
    asyncio.run(debug_zip())
