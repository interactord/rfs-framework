"""
프롬프트 템플릿 시스템 단위 테스트

프롬프트 템플릿의 렌더링과 관리 기능을 테스트합니다.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestPromptTemplate:
    """프롬프트 템플릿 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.prompts.template import PromptTemplate
            self.template_class = PromptTemplate
            self.has_templates = True
        except ImportError:
            self.has_templates = False
    
    def test_template_initialization(self):
        """템플릿 초기화 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        template_str = "안녕하세요, {{ name }}님!"
        variables = ["name"]
        
        template = self.template_class(
            name="greeting",
            template=template_str,
            variables=variables
        )
        
        assert template.name == "greeting"
        assert template.template == template_str
        assert template.variables == variables
    
    def test_render_success(self):
        """템플릿 렌더링 성공 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        template = self.template_class(
            name="greeting",
            template="안녕하세요, {{ name }}님! 오늘은 {{ weather }}입니다.",
            variables=["name", "weather"]
        )
        
        result = template.render({
            "name": "홍길동",
            "weather": "맑음"
        })
        
        assert result.is_success()
        rendered = result.unwrap()
        assert rendered == "안녕하세요, 홍길동님! 오늘은 맑음입니다."
    
    def test_render_missing_variable(self):
        """필수 변수 누락 시 템플릿 렌더링 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        template = self.template_class(
            name="greeting",
            template="안녕하세요, {{ name }}님!",
            variables=["name"]
        )
        
        result = template.render({})  # name 변수 누락
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "name" in error_message
    
    def test_render_with_optional_variable(self):
        """선택적 변수가 있는 템플릿 렌더링 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        template = self.template_class(
            name="greeting",
            template="""안녕하세요, {{ name }}님!
{% if title %}
당신의 직급은 {{ title }}입니다.
{% endif %}""",
            variables=["name"],
            optional_variables=["title"]
        )
        
        # 선택적 변수 없이 렌더링
        result1 = template.render({"name": "홍길동"})
        assert result1.is_success()
        rendered1 = result1.unwrap()
        assert "홍길동" in rendered1
        assert "직급" not in rendered1
        
        # 선택적 변수와 함께 렌더링
        result2 = template.render({"name": "홍길동", "title": "팀장"})
        assert result2.is_success()
        rendered2 = result2.unwrap()
        assert "홍길동" in rendered2
        assert "팀장" in rendered2
    
    def test_validate_variables(self):
        """변수 검증 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        template = self.template_class(
            name="test",
            template="{{ name }}은 {{ age }}살입니다.",
            variables=["name", "age"]
        )
        
        # 유효한 변수들
        result1 = template.validate_variables({"name": "홍길동", "age": 30})
        assert result1.is_success()
        
        # 누락된 변수
        result2 = template.validate_variables({"name": "홍길동"})
        assert result2.is_failure()


@pytest.mark.asyncio
class TestPromptTemplateManager:
    """프롬프트 템플릿 매니저 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.prompts.template import PromptTemplateManager, PromptTemplate
            from rfs.llm.manager import LLMManager
            self.manager_class = PromptTemplateManager
            self.template_class = PromptTemplate
            self.llm_manager_class = LLMManager
            self.has_templates = True
        except ImportError:
            self.has_templates = False
    
    def test_manager_initialization(self):
        """매니저 초기화 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        assert len(manager.templates) == 0
    
    async def test_register_template(self):
        """템플릿 등록 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        template = self.template_class(
            name="test",
            template="{{ message }}",
            variables=["message"]
        )
        
        result = await manager.register_template("test", template)
        
        assert result.is_success()
        assert "test" in manager.templates
        assert manager.templates["test"] == template
    
    async def test_register_template_from_string(self):
        """문자열로부터 템플릿 등록 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        result = await manager.register_template_from_string(
            name="simple",
            template_str="안녕하세요, {{ name }}님!",
            variables=["name"]
        )
        
        assert result.is_success()
        assert "simple" in manager.templates
        
        # 등록된 템플릿 사용 테스트
        template = manager.templates["simple"]
        render_result = template.render({"name": "테스트"})
        assert render_result.is_success()
        assert "테스트" in render_result.unwrap()
    
    async def test_register_common_templates(self):
        """공통 템플릿 등록 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        result = await manager.register_common_templates()
        
        assert result.is_success()
        
        # 공통 템플릿들이 등록되었는지 확인
        expected_templates = ["code_review", "summarization", "translation", "qa"]
        for template_name in expected_templates:
            assert template_name in manager.templates
    
    async def test_render_template_success(self):
        """템플릿 렌더링 성공 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        await manager.register_template_from_string(
            name="test",
            template_str="주제: {{ topic }}, 내용: {{ content }}",
            variables=["topic", "content"]
        )
        
        result = await manager.render_template(
            "test",
            {"topic": "AI", "content": "인공지능에 대한 설명"}
        )
        
        assert result.is_success()
        rendered = result.unwrap()
        assert "AI" in rendered
        assert "인공지능" in rendered
    
    async def test_render_template_not_found(self):
        """존재하지 않는 템플릿 렌더링 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        result = await manager.render_template(
            "nonexistent",
            {"var": "value"}
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "nonexistent" in error_message
    
    async def test_render_and_generate_success(self):
        """템플릿 렌더링 후 LLM 생성 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        # 테스트용 템플릿 등록
        await manager.register_template_from_string(
            name="test",
            template_str="다음 주제에 대해 설명하세요: {{ topic }}",
            variables=["topic"]
        )
        
        # Mock LLM Manager 생성
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        mock_llm_manager.generate = AsyncMock(return_value=Success({
            "response": "AI에 대한 상세한 설명입니다.",
            "model": "test-model",
            "usage": {"total_tokens": 20}
        }))
        
        result = await manager.render_and_generate(
            template_name="test",
            provider="test",
            manager=mock_llm_manager,
            variables={"topic": "인공지능"},
            model="test-model"
        )
        
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data["response"] == "AI에 대한 상세한 설명입니다."
        
        # LLM Manager의 generate가 올바른 프롬프트로 호출되었는지 확인
        mock_llm_manager.generate.assert_called_once()
        call_args = mock_llm_manager.generate.call_args
        assert "인공지능" in call_args[1]["prompt"]
    
    async def test_render_and_generate_template_error(self):
        """템플릿 렌더링 실패 시 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        # 필수 변수가 있는 템플릿 등록
        await manager.register_template_from_string(
            name="test",
            template_str="주제: {{ topic }}",
            variables=["topic"]
        )
        
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        
        # 필수 변수 누락으로 렌더링 실행
        result = await manager.render_and_generate(
            template_name="test",
            provider="test",
            manager=mock_llm_manager,
            variables={},  # topic 누락
            model="test-model"
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "topic" in error_message
        
        # LLM Manager의 generate가 호출되지 않았는지 확인
        mock_llm_manager.generate.assert_not_called()
    
    async def test_render_and_generate_llm_error(self):
        """LLM 생성 실패 시 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        await manager.register_template_from_string(
            name="test",
            template_str="주제: {{ topic }}",
            variables=["topic"]
        )
        
        # LLM 호출 실패 Mock
        mock_llm_manager = Mock(spec=self.llm_manager_class)
        mock_llm_manager.generate = AsyncMock(return_value=Failure("API 호출 실패"))
        
        result = await manager.render_and_generate(
            template_name="test",
            provider="test",
            manager=mock_llm_manager,
            variables={"topic": "인공지능"},
            model="test-model"
        )
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "API 호출 실패" in error_message
    
    def test_list_templates(self):
        """템플릿 목록 조회 테스트"""
        if not self.has_templates:
            pytest.skip("템플릿 모듈을 사용할 수 없습니다")
        
        manager = self.manager_class()
        
        # 처음에는 빈 목록
        templates = manager.list_templates()
        assert len(templates) == 0
        
        # 템플릿 추가 후
        template = self.template_class(
            name="test1",
            template="{{ message }}",
            variables=["message"]
        )
        manager.templates["test1"] = template
        
        template2 = self.template_class(
            name="test2", 
            template="{{ content }}",
            variables=["content"]
        )
        manager.templates["test2"] = template2
        
        templates = manager.list_templates()
        assert len(templates) == 2
        assert "test1" in templates
        assert "test2" in templates