"""
ChromaDB Vector Store 구현

ChromaDB를 사용한 벡터 스토어 구현체입니다.
Result Pattern과 RFS Framework의 모든 패턴을 준수합니다.
"""

from typing import List, Dict, Any, Optional, Union
from rfs.core.result import Result, Success, Failure
from rfs.core.annotations import Service
from .vector_store import VectorStore

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


if CHROMA_AVAILABLE:
    @Service("llm_service")
    class ChromaVectorStore(VectorStore):
        """ChromaDB 구현체
        
        ChromaDB를 사용하여 벡터 저장 및 검색을 제공합니다.
        영속성과 임시 저장소 모두를 지원합니다.
        """
        
        def __init__(
            self, 
            collection_name: str, 
            persist_directory: Optional[str] = None,
            embedding_function: Optional[Any] = None,
            distance_metric: str = "cosine"
        ):
            if not CHROMA_AVAILABLE:
                raise ImportError(
                    "ChromaDB가 설치되지 않았습니다. 'pip install chromadb' 명령으로 설치하세요."
                )
            
            self.collection_name = collection_name
            self.persist_directory = persist_directory
            self.distance_metric = distance_metric
            
            # 클라이언트 설정
            if persist_directory:
                self.client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                self.client = chromadb.EphemeralClient(
                    settings=Settings(anonymized_telemetry=False)
                )
            
            # 컬렉션 생성 또는 가져오기
            try:
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=embedding_function,
                    metadata={"hnsw:space": distance_metric}
                )
            except Exception as e:
                raise RuntimeError(f"ChromaDB 컬렉션 초기화 실패: {str(e)}")
        
        async def add_documents(
            self, 
            documents: List[Dict[str, Any]]
        ) -> Result[List[str], str]:
            """ChromaDB에 문서 추가"""
            try:
                if not documents:
                    return Success([])
                
                ids = []
                texts = []
                metadatas = []
                embeddings = []
                
                for i, doc in enumerate(documents):
                    # 필수 필드 검증
                    if "content" not in doc:
                        return Failure(f"문서 {i}에 'content' 필드가 없습니다")
                    
                    # ID 생성 또는 사용
                    doc_id = doc.get("id", f"doc_{i}_{hash(doc['content']) % 1000000}")
                    ids.append(str(doc_id))
                    texts.append(doc["content"])
                    
                    # 메타데이터 처리
                    metadata = doc.get("metadata", {})
                    # ChromaDB는 메타데이터에 None 값을 허용하지 않음
                    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
                    metadatas.append(clean_metadata)
                    
                    # 임베딩이 제공된 경우
                    if "embedding" in doc:
                        embeddings.append(doc["embedding"])
                
                # ChromaDB에 추가
                add_params = {
                    "documents": texts,
                    "metadatas": metadatas,
                    "ids": ids
                }
                
                if embeddings:
                    add_params["embeddings"] = embeddings
                
                self.collection.add(**add_params)
                
                return Success(ids)
                
            except Exception as e:
                return Failure(f"ChromaDB 문서 추가 실패: {str(e)}")
        
        async def similarity_search(
            self,
            query: str,
            k: int = 5,
            filter_metadata: Optional[Dict[str, Any]] = None,
            **kwargs
        ) -> Result[List[Dict[str, Any]], str]:
            """ChromaDB에서 유사도 검색"""
            try:
                # 쿼리 파라미터 구성
                query_params = {
                    "query_texts": [query],
                    "n_results": k
                }
                
                # 메타데이터 필터 추가
                if filter_metadata:
                    query_params["where"] = filter_metadata
                
                # 추가 파라미터
                if "include" in kwargs:
                    query_params["include"] = kwargs["include"]
                else:
                    query_params["include"] = ["documents", "metadatas", "distances"]
                
                # 검색 실행
                results = self.collection.query(**query_params)
                
                # 결과 변환
                documents = []
                if results["ids"] and len(results["ids"][0]) > 0:
                    for i in range(len(results["ids"][0])):
                        doc = {
                            "id": results["ids"][0][i],
                            "content": results["documents"][0][i] if results["documents"] else "",
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        }
                        
                        # 거리 또는 점수 추가
                        if results["distances"] and i < len(results["distances"][0]):
                            distance = results["distances"][0][i]
                            # 코사인 거리를 유사도로 변환 (0~1 범위)
                            if self.distance_metric == "cosine":
                                doc["similarity"] = max(0.0, 1.0 - distance)
                            doc["distance"] = distance
                        
                        documents.append(doc)
                
                return Success(documents)
                
            except Exception as e:
                return Failure(f"ChromaDB 유사도 검색 실패: {str(e)}")
        
        async def similarity_search_by_vector(
            self,
            embedding: List[float],
            k: int = 5,
            filter_metadata: Optional[Dict[str, Any]] = None,
            **kwargs
        ) -> Result[List[Dict[str, Any]], str]:
            """임베딩 벡터로 유사도 검색"""
            try:
                query_params = {
                    "query_embeddings": [embedding],
                    "n_results": k,
                    "include": kwargs.get("include", ["documents", "metadatas", "distances"])
                }
                
                if filter_metadata:
                    query_params["where"] = filter_metadata
                
                results = self.collection.query(**query_params)
                
                documents = []
                if results["ids"] and len(results["ids"][0]) > 0:
                    for i in range(len(results["ids"][0])):
                        doc = {
                            "id": results["ids"][0][i],
                            "content": results["documents"][0][i] if results["documents"] else "",
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        }
                        
                        if results["distances"] and i < len(results["distances"][0]):
                            distance = results["distances"][0][i]
                            if self.distance_metric == "cosine":
                                doc["similarity"] = max(0.0, 1.0 - distance)
                            doc["distance"] = distance
                        
                        documents.append(doc)
                
                return Success(documents)
                
            except Exception as e:
                return Failure(f"ChromaDB 벡터 검색 실패: {str(e)}")
        
        async def delete_documents(self, ids: List[str]) -> Result[None, str]:
            """ChromaDB에서 문서 삭제"""
            try:
                if not ids:
                    return Success(None)
                
                str_ids = [str(doc_id) for doc_id in ids]
                self.collection.delete(ids=str_ids)
                
                return Success(None)
                
            except Exception as e:
                return Failure(f"ChromaDB 문서 삭제 실패: {str(e)}")
        
        async def update_documents(
            self,
            documents: List[Dict[str, Any]]
        ) -> Result[List[str], str]:
            """ChromaDB에서 문서 업데이트"""
            try:
                if not documents:
                    return Success([])
                
                ids = []
                texts = []
                metadatas = []
                embeddings = []
                
                for doc in documents:
                    if "id" not in doc:
                        return Failure("업데이트할 문서에 ID가 필요합니다")
                    if "content" not in doc:
                        return Failure("업데이트할 문서에 content가 필요합니다")
                    
                    ids.append(str(doc["id"]))
                    texts.append(doc["content"])
                    
                    metadata = doc.get("metadata", {})
                    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
                    metadatas.append(clean_metadata)
                    
                    if "embedding" in doc:
                        embeddings.append(doc["embedding"])
                
                # ChromaDB update
                update_params = {
                    "ids": ids,
                    "documents": texts,
                    "metadatas": metadatas
                }
                
                if embeddings:
                    update_params["embeddings"] = embeddings
                
                self.collection.update(**update_params)
                
                return Success(ids)
                
            except Exception as e:
                return Failure(f"ChromaDB 문서 업데이트 실패: {str(e)}")
        
        async def get_document_by_id(self, doc_id: str) -> Result[Dict[str, Any], str]:
            """ID로 문서 조회"""
            try:
                results = self.collection.get(
                    ids=[str(doc_id)],
                    include=["documents", "metadatas"]
                )
                
                if not results["ids"] or len(results["ids"]) == 0:
                    return Failure(f"문서 ID '{doc_id}'를 찾을 수 없습니다")
                
                doc = {
                    "id": results["ids"][0],
                    "content": results["documents"][0] if results["documents"] else "",
                    "metadata": results["metadatas"][0] if results["metadatas"] else {}
                }
                
                return Success(doc)
                
            except Exception as e:
                return Failure(f"ChromaDB 문서 조회 실패: {str(e)}")
        
        def get_collection_info(self) -> Dict[str, Any]:
            """ChromaDB 컬렉션 정보 반환"""
            try:
                count = self.collection.count()
                
                return {
                    "name": self.collection_name,
                    "count": count,
                    "persist_directory": self.persist_directory,
                    "distance_metric": self.distance_metric,
                    "type": "ChromaDB"
                }
            except Exception as e:
                return {
                    "name": self.collection_name,
                    "error": str(e),
                    "type": "ChromaDB"
                }
        
        def reset_collection(self) -> Result[None, str]:
            """컬렉션 초기화 (모든 데이터 삭제)"""
            try:
                # 기존 컬렉션 삭제
                try:
                    self.client.delete_collection(name=self.collection_name)
                except Exception:
                    pass  # 컬렉션이 존재하지 않을 수 있음
                
                # 새 컬렉션 생성
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": self.distance_metric}
                )
                
                return Success(None)
                
            except Exception as e:
                return Failure(f"ChromaDB 컬렉션 초기화 실패: {str(e)}")
        
        async def get_collection_stats(self) -> Result[Dict[str, Any], str]:
            """컬렉션 통계 반환"""
            try:
                count = self.collection.count()
                
                # 샘플 문서들로 메타데이터 분석
                sample_results = self.collection.get(limit=100, include=["metadatas"])
                
                metadata_keys = set()
                if sample_results["metadatas"]:
                    for metadata in sample_results["metadatas"]:
                        metadata_keys.update(metadata.keys())
                
                stats = {
                    "total_documents": count,
                    "metadata_keys": list(metadata_keys),
                    "collection_name": self.collection_name,
                    "distance_metric": self.distance_metric
                }
                
                return Success(stats)
                
            except Exception as e:
                return Failure(f"ChromaDB 통계 조회 실패: {str(e)}")

else:
    class ChromaVectorStore(VectorStore):
        """ChromaDB가 설치되지 않은 경우의 더미 클래스"""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "ChromaDB가 설치되지 않았습니다. 'pip install chromadb' 명령으로 설치하세요."
            )
        
        async def add_documents(self, documents: List[Dict[str, Any]]) -> Result[List[str], str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        async def similarity_search(self, query: str, k: int = 5, **kwargs) -> Result[List[Dict[str, Any]], str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        async def similarity_search_by_vector(self, embedding: List[float], k: int = 5, **kwargs) -> Result[List[Dict[str, Any]], str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        async def delete_documents(self, ids: List[str]) -> Result[None, str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        async def update_documents(self, documents: List[Dict[str, Any]]) -> Result[List[str], str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        async def get_document_by_id(self, doc_id: str) -> Result[Dict[str, Any], str]:
            return Failure("ChromaDB가 설치되지 않았습니다")
        
        def get_collection_info(self) -> Dict[str, Any]:
            return {"error": "ChromaDB가 설치되지 않았습니다"}