"""
Pool abstractions and utilities for `prompits.core.pool`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the core package defines the
shared abstractions that the rest of the runtime builds on.

Core types exposed here include `DataItem`, `Pool`, `PoolCap`, and
`PoolOperationPractice`, which carry the main behavior or state managed by this module.
"""

import threading
import uuid
from abc import abstractmethod, ABC
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool
from .message import Message
from .practice import Practice
from .pit import Pit, PitAddress
from .schema import DataType, TableSchema

class DataItem(ABC):
    """
    Abstract record-like unit intended for typed objects persisted in a `Pool`.

    `DataItem` is currently a simple contract holder. Concrete subclasses can
    define richer serialization logic via `to_dict`.
    """

    def __init__(self, id: str, name: str, description: str, data_type: DataType):
        """Initialize the data item."""
        self.id = id
        self.name = name
        self.description = description
        self.data_type = data_type

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert the value to dict."""
        pass


class PoolCap(str, Enum):
    """Represent a pool cap."""
    TABLE = "table"
    JSON = "json"
    VECTOR = "vector"
    GRAPH = "graph"
    BLOB = "blob"
    SEARCH = "search"
    MEMORY = "memory"


class PoolOperationPractice(Practice, ABC):
    """
    Abstract practice wrapper for one pool operation.

    Concrete pool implementations publish these practices so the owning agent
    can expose storage operations through the same discovery and invocation
    flow as any other practice.
    """

    def __init__(
        self,
        pool: "Pool",
        name: str,
        description: str,
        id: str,
        parameters: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Union[str, Dict[str, Any]]]] = None,
        tags: Optional[List[str]] = None,
    ):
        """Initialize the pool operation practice."""
        super().__init__(
            name=name,
            description=description,
            id=id,
            tags=tags or ["pool", pool.__class__.__name__.lower()],
            examples=examples or [],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters=parameters or {},
        )
        self.pool = pool

    def mount(self, app: FastAPI):
        """Mount the value."""
        router = APIRouter()

        @router.post(self.path, name=self.id)
        async def invoke(message: Message):
            """Route handler for POST requests."""
            try:
                content = message.content
                if isinstance(content, dict):
                    return await run_in_threadpool(self.execute, **content)
                if content is None:
                    return await run_in_threadpool(self.execute)
                return await run_in_threadpool(self.execute, content=content)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        app.include_router(router)


class _BoundPoolOperationPractice(PoolOperationPractice):
    """Concrete runtime practice bound to a pool operation callback."""

    def __init__(self, executor, **kwargs):
        """Initialize the bound pool operation practice."""
        super().__init__(**kwargs)
        self._executor = executor

    def execute(self, **kwargs) -> Any:
        """Handle execute for the bound pool operation practice."""
        return self._executor(**kwargs)


class Pool(Pit, ABC):
    """
    Storage backend interface used by agents and practices.

    Implementations (filesystem/sqlite/supabase) provide a common CRUD-like
    surface used by runtime components to persist credentials, cards, practice
    metadata, and other state.
    """

    MEMORY_TABLE = "pool_memories"

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        address: Optional[PitAddress] = None,
        meta: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[PoolCap]] = None,
    ):
        """Initialize the pool."""
        super().__init__(
            name=name,
            description=description or f"Pool {name}",
            address=address,
            meta=meta,
        )
        # Lock is available for subclasses that need cross-thread critical sections.
        self.lock = threading.Lock()
        self.is_connected = False
        self.last_error = ""
        self.capabilities: List[PoolCap] = list(capabilities or [])
        self.meta["capabilities"] = [cap.value for cap in self.capabilities]

    @staticmethod
    def _coerce_table_schema(value: Optional[Union[TableSchema, Dict[str, Any]]]) -> Optional[TableSchema]:
        """Internal helper to coerce the table schema."""
        if value is None or isinstance(value, TableSchema):
            return value
        if isinstance(value, dict):
            return TableSchema(value)
        raise ValueError(f"Unsupported table schema value: {type(value).__name__}")

    @classmethod
    def memory_table_schema(cls) -> TableSchema:
        """Return the memory table schema."""
        return TableSchema({
            "name": cls.MEMORY_TABLE,
            "description": "Shared memory records stored in a pool.",
            "primary_key": ["id"],
            "rowSchema": {
                "id": {"type": "string"},
                "content": {"type": "string"},
                "memory_type": {"type": "string"},
                "metadata": {"type": "json"},
                "tags": {"type": "json"},
                "created_at": {"type": "datetime"},
                "updated_at": {"type": "datetime"},
            },
        })

    @staticmethod
    def _serialize_memory_content(content: Any) -> str:
        """Internal helper to serialize the memory content."""
        if isinstance(content, str):
            return content
        if content is None:
            return ""
        try:
            import json
            return json.dumps(content, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(content)

    @classmethod
    def _normalize_memory_record(
        cls,
        content: Any,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        memory_type: str = "text",
    ) -> Dict[str, Any]:
        """Internal helper to normalize the memory record."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": memory_id or str(uuid.uuid4()),
            "content": cls._serialize_memory_content(content),
            "memory_type": memory_type or "text",
            "metadata": dict(metadata or {}),
            "tags": list(tags or []),
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _memory_search_text(record: Dict[str, Any]) -> str:
        """Internal helper for memory search text."""
        tags = record.get("tags") or []
        metadata = record.get("metadata") or {}
        content = str(record.get("content") or "")
        return " ".join([
            content,
            " ".join(str(tag) for tag in tags),
            " ".join(f"{k}:{v}" for k, v in metadata.items()),
        ]).lower()

    def _build_operation_practice(
        self,
        operation_id: str,
        name: str,
        description: str,
        parameters: Optional[Dict[str, Any]],
        executor,
        examples: Optional[List[Union[str, Dict[str, Any]]]] = None,
        tags: Optional[List[str]] = None,
    ) -> Practice:
        """Internal helper to build the operation practice."""
        return _BoundPoolOperationPractice(
            pool=self,
            name=name,
            description=description,
            id=operation_id,
            parameters=parameters,
            examples=examples,
            tags=tags,
            executor=executor,
        )

    @abstractmethod
    def _CreateTable(self, table_name: str, schema: TableSchema):
        """Internal helper to create the table."""
        raise NotImplementedError("CreateTable not implemented")

    @abstractmethod
    def _TableExists(self, table_name: str) -> bool:
        """Return whether the table exists for value."""
        raise NotImplementedError("TableExists not implemented")

    @abstractmethod
    def _Insert(self, table_name: str, data: Dict[str, Any]):
        """Insert data into a table."""
        raise NotImplementedError("Insert not implemented")

    def _InsertMany(self, table_name: str, data_list: List[Dict[str, Any]]):
        """Insert multiple rows into a table.

        Subclasses can override this for efficient bulk writes. The default
        implementation preserves behavior by delegating to `_Insert`.
        """
        for data in data_list or []:
            if not self._Insert(table_name, data):
                return False
        return True
        
    @abstractmethod
    def _Query(self, query: str, params: Union[List[Any], Dict[str, Any]]=None):
        """Internal helper to query the value."""
        raise NotImplementedError("Query not implemented")

    @abstractmethod
    def _GetTableData(self, table_name: str, id_or_where: Union[str, Dict]=None, table_schema: TableSchema=None) -> List[Dict[str, Any]]:
        """Internal helper to return the table data."""
        raise NotImplementedError("GetTableData not implemented")

    @abstractmethod
    def create_table_practice(self) -> Practice:
        """Create the table practice."""
        raise NotImplementedError("create_table_practice not implemented")

    @abstractmethod
    def table_exists_practice(self) -> Practice:
        """Return whether the table exists for practice."""
        raise NotImplementedError("table_exists_practice not implemented")

    @abstractmethod
    def insert_practice(self) -> Practice:
        """Handle insert practice for the pool."""
        raise NotImplementedError("insert_practice not implemented")

    @abstractmethod
    def query_practice(self) -> Practice:
        """Query the practice."""
        raise NotImplementedError("query_practice not implemented")

    @abstractmethod
    def get_table_data_practice(self) -> Practice:
        """Return the table data practice."""
        raise NotImplementedError("get_table_data_practice not implemented")

    @abstractmethod
    def store_memory(
        self,
        content: Any,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        memory_type: str = "text",
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle store memory for the pool."""
        raise NotImplementedError("store_memory not implemented")

    @abstractmethod
    def search_memory(
        self,
        query: str,
        limit: int = 10,
        table_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search the memory."""
        raise NotImplementedError("search_memory not implemented")

    @abstractmethod
    def store_memory_practice(self) -> Practice:
        """Handle store memory practice for the pool."""
        raise NotImplementedError("store_memory_practice not implemented")

    @abstractmethod
    def search_memory_practice(self) -> Practice:
        """Search the memory practice."""
        raise NotImplementedError("search_memory_practice not implemented")

    @abstractmethod
    def connect(self):
        """Connect to underlying storage."""
        raise NotImplementedError("connect not implemented")

    @abstractmethod
    def disconnect(self):
        """Disconnect from underlying storage."""
        raise NotImplementedError("disconnect not implemented")

    @abstractmethod
    def connect_practice(self) -> Practice:
        """Connect the practice."""
        raise NotImplementedError("connect_practice not implemented")

    @abstractmethod
    def disconnect_practice(self) -> Practice:
        """Disconnect the practice."""
        raise NotImplementedError("disconnect_practice not implemented")

    def get_operation_practices(self) -> List[Practice]:
        """Return the operation practices."""
        return [
            self.connect_practice(),
            self.disconnect_practice(),
            self.create_table_practice(),
            self.table_exists_practice(),
            self.insert_practice(),
            self.query_practice(),
            self.get_table_data_practice(),
            self.store_memory_practice(),
            self.search_memory_practice(),
        ]
