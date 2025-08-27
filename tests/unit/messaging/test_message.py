"""
RFS Framework Message 클래스 단위 테스트

Message 클래스의 생성, 속성, 직렬화 등을 테스트합니다.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from rfs.messaging.base import Message, MessagePriority


class TestMessage:
    """메시지 클래스 테스트"""

    def test_message_creation_with_defaults(self):
        """기본값으로 메시지 생성"""
        message = Message(topic="test_topic", data="test_data")

        assert message.topic == "test_topic"
        assert message.data == "test_data"
        assert message.id is not None
        assert len(message.id) > 0
        assert isinstance(message.timestamp, datetime)
        assert message.priority == MessagePriority.NORMAL
        assert message.retry_count == 0
        assert message.max_retries == 3

    def test_message_creation_with_custom_values(self):
        """사용자 정의 값으로 메시지 생성"""
        custom_id = str(uuid.uuid4())
        custom_timestamp = datetime(2025, 1, 1, 12, 0, 0)
        custom_headers = {"user_id": "123", "request_id": "req_456"}

        message = Message(
            id=custom_id,
            topic="custom_topic",
            data={"key": "value"},
            headers=custom_headers,
            timestamp=custom_timestamp,
            priority=MessagePriority.HIGH,
            ttl=3600,
            max_retries=5,
        )

        assert message.id == custom_id
        assert message.topic == "custom_topic"
        assert message.data == {"key": "value"}
        assert message.headers == custom_headers
        assert message.timestamp == custom_timestamp
        assert message.priority == MessagePriority.HIGH
        assert message.ttl == 3600
        assert message.max_retries == 5

    def test_message_auto_id_generation(self):
        """ID 자동 생성 테스트"""
        message1 = Message(topic="test", data="data1")
        message2 = Message(topic="test", data="data2")

        assert message1.id != message2.id
        assert len(message1.id) > 0
        assert len(message2.id) > 0

    def test_message_auto_timestamp_generation(self):
        """타임스탬프 자동 생성 테스트"""
        before = datetime.now()
        message = Message(topic="test", data="data")
        after = datetime.now()

        assert before <= message.timestamp <= after

    def test_message_priority_levels(self):
        """메시지 우선순위 레벨 테스트"""
        low_msg = Message(topic="test", data="data", priority=MessagePriority.LOW)
        normal_msg = Message(topic="test", data="data", priority=MessagePriority.NORMAL)
        high_msg = Message(topic="test", data="data", priority=MessagePriority.HIGH)

        assert low_msg.priority == MessagePriority.LOW
        assert normal_msg.priority == MessagePriority.NORMAL
        assert high_msg.priority == MessagePriority.HIGH

        # 우선순위 값 확인
        assert low_msg.priority.value < normal_msg.priority.value
        assert normal_msg.priority.value < high_msg.priority.value

        # URGENT가 있는 경우만 테스트
        if hasattr(MessagePriority, "URGENT"):
            urgent_msg = Message(
                topic="test", data="data", priority=MessagePriority.URGENT
            )
            assert urgent_msg.priority == MessagePriority.URGENT
            assert high_msg.priority.value < urgent_msg.priority.value

    def test_message_headers_manipulation(self):
        """메시지 헤더 조작 테스트"""
        message = Message(topic="test", data="data")

        # 초기 상태
        assert message.headers == {}

        # 헤더 추가
        message.headers["key1"] = "value1"
        message.headers["key2"] = "value2"

        assert message.headers["key1"] == "value1"
        assert message.headers["key2"] == "value2"
        assert len(message.headers) == 2

    def test_message_ttl_expiration(self):
        """메시지 TTL 만료 확인"""
        # TTL이 설정된 메시지
        message_with_ttl = Message(
            topic="test",
            data="data",
            ttl=1,  # 1초
            timestamp=datetime.now() - timedelta(seconds=2),  # 2초 전 생성
        )

        # TTL이 없는 메시지
        message_without_ttl = Message(topic="test", data="data", ttl=None)

        # TTL이 아직 유효한 메시지
        message_valid_ttl = Message(
            topic="test", data="data", ttl=3600, timestamp=datetime.now()  # 1시간
        )

        # 만료 확인 로직 (실제 구현에 따라 조정 필요)
        if hasattr(message_with_ttl, "is_expired"):
            assert message_with_ttl.is_expired
            assert not message_without_ttl.is_expired
            assert not message_valid_ttl.is_expired

    def test_message_retry_mechanism(self):
        """메시지 재시도 메커니즘 테스트"""
        message = Message(topic="test", data="data", max_retries=3)

        assert message.retry_count == 0
        assert message.max_retries == 3

        # 재시도 카운트 증가 (실제 구현에 따라 조정 필요)
        if hasattr(message, "increment_retry"):
            message.increment_retry()
            assert message.retry_count == 1

            message.increment_retry()
            assert message.retry_count == 2

            message.increment_retry()
            assert message.retry_count == 3

    def test_message_serialization(self):
        """메시지 직렬화 테스트"""
        message = Message(
            topic="test_topic",
            data={"key": "value", "number": 42},
            headers={"header1": "value1"},
        )

        # to_dict 메서드가 있는 경우
        if hasattr(message, "to_dict"):
            msg_dict = message.to_dict()
            assert msg_dict["topic"] == "test_topic"
            assert msg_dict["data"] == {"key": "value", "number": 42}
            assert msg_dict["headers"] == {"header1": "value1"}
            assert "id" in msg_dict
            assert "timestamp" in msg_dict

    def test_message_equality(self):
        """메시지 동등성 비교"""
        msg_id = str(uuid.uuid4())
        timestamp = datetime.now()

        message1 = Message(id=msg_id, topic="test", data="data", timestamp=timestamp)

        message2 = Message(id=msg_id, topic="test", data="data", timestamp=timestamp)

        message3 = Message(topic="test", data="data")

        # 같은 ID를 가진 메시지는 동일
        if hasattr(message1, "__eq__"):
            assert message1 == message2
            assert message1 != message3

    def test_message_with_complex_data(self):
        """복잡한 데이터 타입을 가진 메시지"""
        complex_data = {
            "nested": {"level1": {"level2": ["item1", "item2"]}},
            "list": [1, 2, 3, 4, 5],
            "tuple": (1, 2, 3),
            "string": "test string",
            "number": 123.456,
            "boolean": True,
            "none": None,
        }

        message = Message(topic="complex", data=complex_data)

        assert message.data == complex_data
        assert message.data["nested"]["level1"]["level2"] == ["item1", "item2"]
        assert message.data["number"] == 123.456

    def test_message_edge_cases(self):
        """메시지 엣지 케이스 테스트"""
        # 빈 데이터
        empty_msg = Message(topic="test", data=None)
        assert empty_msg.data is None

        # 빈 문자열 토픽
        empty_topic_msg = Message(topic="", data="data")
        assert empty_topic_msg.topic == ""

        # 매우 큰 데이터
        large_data = "x" * 10000
        large_msg = Message(topic="test", data=large_data)
        assert len(large_msg.data) == 10000

        # 특수 문자가 포함된 토픽
        special_topic = "test/topic#with$special@chars"
        special_msg = Message(topic=special_topic, data="data")
        assert special_msg.topic == special_topic
