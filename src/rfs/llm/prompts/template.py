"""
프롬프트 템플릿 시스템

Jinja2를 기반으로 한 동적 프롬프트 템플릿 생성 및 관리 시스템입니다.
Result Pattern과 HOF 패턴을 완전히 지원합니다.
"""

from typing import Dict, Any, Optional, List, Set
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from rfs.hof.core import pipe

try:
    from jinja2 import Template, Environment, BaseLoader, meta
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class PromptTemplate:
    """프롬프트 템플릿 관리
    
    Jinja2를 사용하여 동적 프롬프트를 생성하고 관리합니다.
    변수 유효성 검증과 안전한 렌더링을 제공합니다.
    """
    
    def __init__(self, template: str, name: Optional[str] = None):
        if not JINJA2_AVAILABLE:
            raise ImportError(
                "Jinja2가 설치되지 않았습니다. 'pip install jinja2' 명령으로 설치하세요."
            )
        
        self.template = template
        self.name = name
        self._jinja_template = Template(template)
        self._template_vars = self._extract_template_variables()
    
    def _extract_template_variables(self) -> Set[str]:
        """템플릿에서 사용된 변수들을 추출합니다"""
        try:
            env = Environment()
            ast = env.parse(self.template)
            return meta.find_undeclared_variables(ast)
        except Exception:
            # 파싱 실패 시 빈 집합 반환
            return set()
    
    def get_required_variables(self) -> List[str]:
        """템플릿에 필요한 변수 목록을 반환합니다
        
        Returns:
            List[str]: 필요한 변수명 목록
        """
        return list(self._template_vars)
    
    def validate_variables(self, variables: Dict[str, Any]) -> Result[None, str]:
        """템플릿 변수 유효성 검증
        
        Args:
            variables: 검증할 변수 딕셔너리
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        try:
            # 누락된 변수 확인
            provided_vars = set(variables.keys())
            missing_vars = self._template_vars - provided_vars
            
            if missing_vars:
                return Failure(
                    f"누락된 템플릿 변수들: {', '.join(sorted(missing_vars))}"
                )
            
            # 변수값 타입 검증 (기본적인 직렬화 가능한 타입인지 확인)
            for key, value in variables.items():
                if not self._is_serializable(value):
                    return Failure(
                        f"변수 '{key}'의 값이 템플릿에서 사용할 수 없는 타입입니다: {type(value)}"
                    )
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"변수 유효성 검증 실패: {str(e)}")
    
    def _is_serializable(self, value: Any) -> bool:
        """값이 템플릿에서 사용 가능한지 확인"""
        try:
            # 기본 타입들
            if value is None or isinstance(value, (str, int, float, bool)):
                return True
            
            # 컬렉션 타입들
            if isinstance(value, (list, tuple, dict)):
                return True
            
            # 문자열로 변환 가능한 객체들
            if hasattr(value, '__str__'):
                return True
            
            return False
        except Exception:
            return False
    
    def render(self, **kwargs) -> Result[str, str]:
        """템플릿 렌더링
        
        Args:
            **kwargs: 템플릿 변수들
            
        Returns:
            Result[str, str]: 성공시 렌더링된 텍스트, 실패시 에러 메시지
        """
        try:
            # 변수 유효성 검증
            validation_result = self.validate_variables(kwargs)
            if validation_result.is_failure():
                return validation_result
            
            # 템플릿 렌더링
            rendered = self._jinja_template.render(**kwargs)
            return Success(rendered)
            
        except Exception as e:
            return Failure(f"템플릿 렌더링 실패: {str(e)}")
    
    def render_safe(self, **kwargs) -> str:
        """안전한 템플릿 렌더링 (에러 시 원본 템플릿 반환)
        
        Args:
            **kwargs: 템플릿 변수들
            
        Returns:
            str: 렌더링된 텍스트 또는 원본 템플릿
        """
        result = self.render(**kwargs)
        if result.is_success():
            return result.unwrap()
        else:
            return self.template  # 에러 시 원본 템플릿 반환
    
    def preview(self, **kwargs) -> Result[str, str]:
        """템플릿 미리보기 (일부 변수만으로도 렌더링 시도)
        
        Args:
            **kwargs: 사용 가능한 템플릿 변수들
            
        Returns:
            Result[str, str]: 부분 렌더링된 텍스트 또는 에러 메시지
        """
        try:
            # 누락된 변수는 플레이스홀더로 대체
            preview_vars = kwargs.copy()
            for var in self._template_vars:
                if var not in preview_vars:
                    preview_vars[var] = f"[{var}]"
            
            rendered = self._jinja_template.render(**preview_vars)
            return Success(rendered)
            
        except Exception as e:
            return Failure(f"템플릿 미리보기 실패: {str(e)}")
    
    def get_info(self) -> Dict[str, Any]:
        """템플릿 정보 반환"""
        return {
            "name": self.name,
            "template_length": len(self.template),
            "required_variables": self.get_required_variables(),
            "variable_count": len(self._template_vars)
        }


@Service("prompt_template_manager")
class PromptTemplateManager:
    """프롬프트 템플릿 관리자
    
    여러 템플릿을 등록하고 관리하며, LLM과의 통합을 제공합니다.
    """
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
    
    def register_template(
        self, 
        name: str, 
        template: str
    ) -> Result[None, str]:
        """템플릿 등록
        
        Args:
            name: 템플릿 이름
            template: 템플릿 문자열
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        try:
            if name in self._templates:
                return Failure(f"템플릿 '{name}'가 이미 존재합니다")
            
            prompt_template = PromptTemplate(template, name)
            self._templates[name] = prompt_template
            return Success(None)
            
        except Exception as e:
            return Failure(f"템플릿 등록 실패: {str(e)}")
    
    def update_template(
        self, 
        name: str, 
        template: str
    ) -> Result[None, str]:
        """기존 템플릿 업데이트
        
        Args:
            name: 템플릿 이름
            template: 새로운 템플릿 문자열
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        try:
            prompt_template = PromptTemplate(template, name)
            self._templates[name] = prompt_template
            return Success(None)
            
        except Exception as e:
            return Failure(f"템플릿 업데이트 실패: {str(e)}")
    
    def unregister_template(self, name: str) -> Result[None, str]:
        """템플릿 등록 해제
        
        Args:
            name: 삭제할 템플릿 이름
            
        Returns:
            Result[None, str]: 성공시 None, 실패시 에러 메시지
        """
        if name not in self._templates:
            return Failure(f"템플릿 '{name}'를 찾을 수 없습니다")
        
        try:
            del self._templates[name]
            return Success(None)
        except Exception as e:
            return Failure(f"템플릿 삭제 실패: {str(e)}")
    
    def get_template(self, name: str) -> Result[PromptTemplate, str]:
        """템플릿 조회
        
        Args:
            name: 조회할 템플릿 이름
            
        Returns:
            Result[PromptTemplate, str]: 성공시 템플릿, 실패시 에러 메시지
        """
        if name not in self._templates:
            return Failure(f"템플릿 '{name}'를 찾을 수 없습니다")
        
        return Success(self._templates[name])
    
    def list_templates(self) -> List[str]:
        """등록된 모든 템플릿 이름 목록 반환
        
        Returns:
            List[str]: 템플릿 이름 목록
        """
        return list(self._templates.keys())
    
    def render_template(
        self, 
        name: str, 
        **variables
    ) -> Result[str, str]:
        """템플릿 렌더링
        
        Args:
            name: 템플릿 이름
            **variables: 템플릿 변수들
            
        Returns:
            Result[str, str]: 렌더링된 텍스트 또는 에러 메시지
        """
        template_result = self.get_template(name)
        if template_result.is_failure():
            return template_result
        
        template = template_result.unwrap()
        return template.render(**variables)
    
    async def render_and_generate(
        self,
        template_name: str,
        llm_manager: 'LLMManager',
        model: str,
        variables: Dict[str, Any],
        provider: Optional[str] = None,
        **kwargs
    ) -> Result[str, str]:
        """템플릿 렌더링 후 LLM 생성 (HOF 파이프라인)
        
        Args:
            template_name: 템플릿 이름
            llm_manager: LLM Manager 인스턴스
            model: 사용할 모델명
            variables: 템플릿 변수들
            provider: LLM Provider 이름
            **kwargs: LLM 생성 추가 파라미터
            
        Returns:
            Result[str, str]: 생성된 텍스트 또는 에러 메시지
        """
        # HOF 파이프라인 사용
        return await pipe(
            lambda: self.get_template(template_name),
            lambda template_result: template_result.bind(
                lambda template: template.validate_variables(variables).bind(
                    lambda _: template.render(**variables)
                )
            ),
            lambda prompt_result: prompt_result.bind(
                lambda prompt: llm_manager.generate(
                    prompt=prompt, 
                    model=model, 
                    provider=provider,
                    **kwargs
                )
            )
        )()
    
    def validate_template_variables(
        self, 
        name: str, 
        variables: Dict[str, Any]
    ) -> Result[None, str]:
        """특정 템플릿의 변수 유효성 검증
        
        Args:
            name: 템플릿 이름
            variables: 검증할 변수들
            
        Returns:
            Result[None, str]: 검증 결과
        """
        template_result = self.get_template(name)
        if template_result.is_failure():
            return template_result
        
        template = template_result.unwrap()
        return template.validate_variables(variables)
    
    def get_template_info(self, name: str) -> Result[Dict[str, Any], str]:
        """특정 템플릿 정보 반환
        
        Args:
            name: 템플릿 이름
            
        Returns:
            Result[Dict[str, Any], str]: 템플릿 정보 또는 에러 메시지
        """
        template_result = self.get_template(name)
        if template_result.is_failure():
            return template_result
        
        template = template_result.unwrap()
        return Success(template.get_info())
    
    def get_all_templates_info(self) -> Dict[str, Any]:
        """모든 템플릿 정보 반환
        
        Returns:
            Dict[str, Any]: 모든 템플릿 정보
        """
        info = {}
        for name, template in self._templates.items():
            info[name] = template.get_info()
        
        return {
            "templates": info,
            "total_count": len(self._templates)
        }
    
    def register_common_templates(self) -> Result[None, str]:
        """일반적으로 사용되는 템플릿들을 등록합니다
        
        Returns:
            Result[None, str]: 등록 결과
        """
        common_templates = {
            "simple_question": "질문: {{ question }}\n답변:",
            
            "code_review": """다음 {{ language }} 코드를 리뷰해주세요:

```{{ language }}
{{ code }}
```

리뷰 요청사항:
{% if focus %}
- 특히 {{ focus }}에 집중해서 검토해주세요
{% endif %}
{% if style_guide %}
- {{ style_guide }} 스타일 가이드를 준수하는지 확인해주세요
{% endif %}

개선사항과 권장사항을 제공해주세요.""",
            
            "summarization": """다음 텍스트를 {{ max_length | default(200) }}자 이내로 요약해주세요:

{{ text }}

{% if focus %}
요약 시 {{ focus }}에 중점을 두어주세요.
{% endif %}""",
            
            "translation": """다음 텍스트를 {{ source_lang }}에서 {{ target_lang }}로 번역해주세요:

{{ text }}

{% if style %}
번역 스타일: {{ style }}
{% endif %}
{% if context %}
맥락: {{ context }}
{% endif %}""",
            
            "explanation": """{{ topic }}에 대해 {% if audience %}{{ audience }}를 위해{% endif %} 설명해주세요.

{% if level %}
설명 수준: {{ level }}
{% endif %}
{% if focus_areas %}
특히 다음 영역에 집중해주세요:
{% for area in focus_areas %}
- {{ area }}
{% endfor %}
{% endif %}
{% if examples %}
구체적인 예시를 포함해주세요.
{% endif %}"""
        }
        
        try:
            for name, template in common_templates.items():
                result = self.register_template(name, template)
                if result.is_failure():
                    return result
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"공통 템플릿 등록 실패: {str(e)}")


# Jinja2가 없는 경우를 위한 더미 클래스들
if not JINJA2_AVAILABLE:
    class PromptTemplate:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Jinja2가 설치되지 않았습니다. 'pip install jinja2' 명령으로 설치하세요."
            )
    
    class PromptTemplateManager:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Jinja2가 설치되지 않았습니다. 'pip install jinja2' 명령으로 설치하세요."
            )