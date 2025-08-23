# RFS Framework MCP 서버

RFS (Reactive Functional Serverless) Framework용 MCP (Model Context Protocol) 서버입니다.

## 설치 및 설정

### 1. 의존성 설치
```bash
pip install mcp
```

### 2. Claude Desktop 설정

Claude Desktop의 설정 파일(`claude_desktop_config.json`)에 다음을 추가하세요:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rfs-framework": {
      "command": "python",
      "args": ["/rfs-framework/mcp_server.py"],
      "env": {},
      "cwd": "/rfs-framework"
    }
  }
}
```

### 3. 서버 실행 테스트
```bash
cd /rfs-framework
python mcp_server.py
```

## 제공 기능

### 📚 리소스 (Documentation)
- `rfs://framework/overview` - 프레임워크 개요
- `rfs://patterns/reactive` - 리액티브 패턴 (Flux/Mono)
- `rfs://patterns/functional` - 함수형 프로그래밍 패턴
- `rfs://patterns/serverless` - 서버리스 최적화 패턴
- `rfs://patterns/state-machine` - 상태 머신 패턴
- `rfs://patterns/di` - 의존성 주입 패턴
- `rfs://patterns/events` - 이벤트 기반 아키텍처
- `rfs://examples/basic` - 기본 사용 예제
- `rfs://examples/advanced` - 고급 사용 예제
- `rfs://api/reference` - API 레퍼런스

### 🛠️ 도구 (Tools)
- `generate_rfs_code` - RFS 패턴 기반 코드 생성
- `explain_rfs_pattern` - RFS 패턴 상세 설명
- `suggest_rfs_best_practices` - 베스트 프랙티스 제안
- `validate_rfs_implementation` - RFS 구현 검증

## 사용 예시

### 1. 리액티브 스트림 코드 생성
```
@rfs-framework 리액티브 스트림으로 파일 처리 코드 생성해줘
```

### 2. 함수형 프로그래밍 패턴 적용
```
@rfs-framework 이 코드를 함수형으로 바꿔줘
```

### 3. 서버리스 최적화
```
@rfs-framework Cloud Run 최적화 패턴 적용해줘
```

### 4. 상태 머신 구현
```
@rfs-framework 주문 처리 상태 머신 만들어줘
```

## 지원하는 패턴들

### 🌊 Reactive Patterns
- **Flux**: 0-N 비동기 스트림
- **Mono**: 0-1 비동기 값
- **Operators**: map, filter, flatMap 등
- **Backpressure**: 압력 제어

### 🔧 Functional Patterns
- **Pure Functions**: 순수 함수
- **Immutable Data**: 불변 데이터
- **Function Composition**: 함수 합성
- **Railway Oriented Programming**: Result 타입

### ☁️ Serverless Patterns
- **Cold Start Optimization**: 콜드 스타트 최적화
- **Resource Monitoring**: 리소스 모니터링
- **Instance Warming**: 인스턴스 워밍
- **Memory Management**: 메모리 관리

### 🏭 State Machine Patterns
- **States & Transitions**: 상태와 전이
- **Guards & Actions**: 가드와 액션
- **Hierarchical States**: 계층적 상태
- **Persistence**: 상태 영속성

### 🔌 Dependency Injection
- **Stateless Singleton**: 무상태 싱글톤
- **Lifecycle Management**: 생명주기 관리
- **Configuration**: 설정 관리

### 📡 Event-Driven Architecture
- **Event Bus**: 이벤트 버스
- **Event Store**: 이벤트 저장소
- **Saga Pattern**: 사가 패턴
- **CQRS**: 명령 쿼리 분리

## 문제 해결

### MCP 서버 연결 실패
1. Python 경로 확인
2. 작업 디렉토리 확인
3. 의존성 설치 확인: `pip install mcp`

### 코드 생성 오류
1. 패턴 이름 정확히 입력
2. 상세한 요구사항 제공
3. 컨텍스트 정보 충분히 제공

## 버전 정보
- RFS Framework: v1.0.2
- MCP Protocol: v0.1.0
- Python: 3.9+