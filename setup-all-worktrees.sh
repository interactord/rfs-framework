#!/bin/bash
# 모든 worktree 한번에 설정하기

echo "🚀 RFS Framework - 모든 Worktree 설정 시작"

# 메인 프로젝트에 필요한 파일 복사
echo "📁 필요한 파일 복사 중..."
for worktree in rfs-framework-async-tests rfs-framework-database-tests rfs-framework-analytics-tests; do
    if [ -d "$worktree" ]; then
        cp requirements-test-minimal.txt "$worktree/"
        cp setup-worktree.sh "$worktree/"
        chmod +x "$worktree/setup-worktree.sh"
        echo "  ✓ $worktree 파일 복사 완료"
    fi
done

# 병렬로 각 worktree 설정
echo "⚡ 병렬 환경 설정 시작..."

# async-tests 설정
(cd rfs-framework-async-tests && ./setup-worktree.sh > setup.log 2>&1 && echo "  ✅ async-tests 설정 완료") &
PID1=$!

# database-tests 설정
(cd rfs-framework-database-tests && ./setup-worktree.sh > setup.log 2>&1 && echo "  ✅ database-tests 설정 완료") &
PID2=$!

# analytics-tests 설정
(cd rfs-framework-analytics-tests && ./setup-worktree.sh > setup.log 2>&1 && echo "  ✅ analytics-tests 설정 완료") &
PID3=$!

# 모든 프로세스 대기
echo "⏳ 설정 진행 중... (약 1-2분 소요)"
wait $PID1 $PID2 $PID3

echo ""
echo "🎉 모든 Worktree 설정 완료!"
echo ""
echo "📝 각 Worktree에서 작업하는 방법:"
echo ""
echo "1️⃣ Async Tasks 테스트:"
echo "   cd rfs-framework-async-tests"
echo "   source venv/bin/activate"
echo "   pytest tests/unit/async_tasks/ -v --cov=rfs.async_tasks"
echo ""
echo "2️⃣ Database 테스트:"
echo "   cd rfs-framework-database-tests"
echo "   source venv/bin/activate"
echo "   pytest tests/unit/database/ -v --cov=rfs.database"
echo ""
echo "3️⃣ Analytics 테스트:"
echo "   cd rfs-framework-analytics-tests"
echo "   source venv/bin/activate"
echo "   pytest tests/unit/analytics/ -v --cov=rfs.analytics"
echo ""
echo "💡 팁: tmux나 여러 터미널을 사용하여 동시에 작업하세요!"