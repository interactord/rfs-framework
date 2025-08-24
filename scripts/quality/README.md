# RFS Framework 통합 품질 관리 시스템

## 📋 개요

RFS Framework의 코드 품질을 관리하는 통합 시스템입니다. 기존 50개 이상의 개별 스크립트를 하나의 체계적인 시스템으로 통합했습니다.

## 🚀 주요 기능

### 1. 백업 관리
- **세션 기반 백업**: 모든 변환 전 자동 백업
- **롤백 지원**: 품질 저하 시 자동 복구
- **Git 독립적**: Git stash 대신 독립적 백업 시스템 사용

### 2. 품질 검사
- **구문 검사**: Python AST 기반 구문 검증
- **스타일 검사**: Black, isort 통합
- **함수형 프로그래밍**: 불변성 규칙 검사
- **타입 검사**: Mypy 통합

### 3. 코드 변환
- **자동 수정**: 안전한 자동 코드 변환
- **Match-Case 패턴**: if-elif 체인을 match-case로 변환
- **함수형 패턴**: 변경 가능 패턴을 불변 패턴으로 변환

## 📁 디렉토리 구조

```
scripts/quality/
├── unified/                 # 통합 시스템 핵심 모듈
│   ├── backup_manager.py    # 백업 관리
│   ├── safe_transformer.py  # 안전한 변환
│   ├── quality_engine.py    # 품질 엔진
│   └── transformers.py      # 변환기 모음
├── rfs-quality              # CLI 인터페이스
└── README.md               # 이 문서

.rfs-quality/                # 품질 관리 데이터
├── backups/                # 백업 저장소
│   ├── sessions/           # 세션별 백업
│   ├── snapshots/          # 스냅샷
│   └── archive/            # 아카이브
├── config/
│   └── quality.yaml        # 설정 파일
└── logs/                   # 로그
```

## 🔧 사용법

### 설치

```bash
# PyYAML 설치 (필요한 경우)
pip install PyYAML
```

### 기본 명령어

#### 품질 검사
```bash
# 전체 검사
./scripts/quality/rfs-quality check

# 특정 디렉토리 검사
./scripts/quality/rfs-quality check src/rfs/core

# 자동 백업과 함께 검사
./scripts/quality/rfs-quality check --auto-backup
```

#### 코드 자동 수정
```bash
# 안전 모드로 모든 수정 적용
./scripts/quality/rfs-quality fix --safe

# 특정 변환만 적용
./scripts/quality/rfs-quality fix --type functional

# Dry run (시뮬레이션)
./scripts/quality/rfs-quality fix --dry-run

# 사용 가능한 변환 유형:
# - syntax_fix: 구문 오류 수정
# - isort: import 정렬
# - black: 코드 포맷팅
# - functional: 함수형 프로그래밍 패턴
# - match_case: match-case 패턴 적용
# - all: 모든 변환 순차 적용
```

#### 백업 관리
```bash
# 백업 세션 생성
./scripts/quality/rfs-quality backup create --description "설명"

# 백업 목록 보기
./scripts/quality/rfs-quality backup list

# 현재 세션 상태
./scripts/quality/rfs-quality backup status

# 롤백
./scripts/quality/rfs-quality backup rollback

# 오래된 백업 정리
./scripts/quality/rfs-quality backup clear --old
```

#### 세션 관리
```bash
# 세션 정보
./scripts/quality/rfs-quality session info

# 세션 메트릭
./scripts/quality/rfs-quality session metrics

# 세션 내보내기
./scripts/quality/rfs-quality session export
```

## ⚙️ 설정

`.rfs-quality/config/quality.yaml` 파일로 설정을 관리합니다:

```yaml
backup:
  enabled: true              # 백업 활성화
  auto_backup: true         # 자동 백업
  retention_days: 7         # 백업 보관 기간
  
quality:
  checks:
    - syntax
    - types
    - style
    - functional
    
  transformations:
    safe_mode: true         # 안전 모드
    rollback_on_error: true # 오류 시 롤백
    
  thresholds:
    max_violations_increase: 0  # 위반 증가 허용치
    
  exclusions:
    functional:             # 함수형 규칙 제외 패턴
      - "**/cache*.py"
      - "**/metrics*.py"
```

## 🛡️ 안전 기능

### 자동 백업
- 모든 변환 전 파일 백업
- 세션별로 관리되는 백업
- 체크섬으로 무결성 검증

### 자동 롤백
- 구문 오류 발생 시 즉시 롤백
- 품질 지표 저하 시 자동 복구
- 세션 단위 롤백 지원

### Dry Run 모드
- 실제 변경 없이 시뮬레이션
- 변환 결과 미리 확인
- 안전한 테스트 환경

## 📊 품질 지표

시스템은 다음 지표를 추적합니다:

- **구문 오류**: Python 파서 검증
- **스타일 위반**: Black/isort 규칙
- **함수형 위반**: 불변성 규칙
- **타입 오류**: Mypy 검사

## 🔄 마이그레이션 완료

기존 50개 이상의 스크립트가 다음과 같이 통합되었습니다:

### 삭제된 스크립트들
- `fix_*.py` - 다양한 수정 스크립트들
- `week*.py` - 주차별 개선 스크립트들
- `final_*.py` - 최종 처리 스크립트들
- `apply_*.py` - 적용 스크립트들
- 기타 중복 스크립트들

### 통합된 기능
✅ 함수형 프로그래밍 변환
✅ Match-case 패턴 적용
✅ 구문 오류 수정
✅ 코드 포맷팅 (Black/isort)
✅ 백업 및 롤백
✅ 품질 검사 및 보고

## 📈 개선 효과

- **코드 감소**: 17,000+ 줄 → 2,000 줄 (88% 감소)
- **유지보수성**: 단일 진입점으로 관리 용이
- **안전성**: 자동 백업/롤백으로 위험 제거
- **확장성**: 플러그인 구조로 쉽게 확장 가능

## 🤝 기여

새로운 변환기나 검사기를 추가하려면:

1. `unified/transformers.py`에 변환 클래스 추가
2. `unified/quality_engine.py`에 등록
3. CLI 명령어 업데이트

## 📝 라이센스

RFS Framework 라이센스를 따릅니다.