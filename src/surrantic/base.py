import json
import logging
import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, ClassVar, Generator, List, Optional, Type, TypeVar, Union

from dotenv import load_dotenv
from pydantic import BaseModel, field_serializer
from surrealdb import AsyncSurrealDB, RecordID, SurrealDB  # type: ignore

from .logging_config import setup_logging

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(logging.DEBUG)

# Get database configuration from environment
SURREAL_ADDRESS = os.getenv("SURREAL_ADDRESS", "ws://localhost:8000")
SURREAL_USER = os.getenv("SURREAL_USER", "root")
SURREAL_PASS = os.getenv("SURREAL_PASS", "root")
SURREAL_NAMESPACE = os.getenv("SURREAL_NAMESPACE", "test")
SURREAL_DATABASE = os.getenv("SURREAL_DATABASE", "test")

T = TypeVar("T", bound="ObjectModel")
logger = logging.getLogger(__name__)

def _prepare_value(value: Any) -> str:
    """Convert Python value to SurrealDBQL value format"""
    if isinstance(value, datetime):
        return f"'{value.isoformat()}'"
    if isinstance(value, RecordID):
        return str(value)
    return json.dumps(value)

def _prepare_data(obj: BaseModel) -> str:
    """Convert Pydantic model to SurrealQL object format using model fields"""
    items = []
    for field_name, field in obj.model_fields.items():
        value = getattr(obj, field_name)
        if value is not None:
            items.append(f"{field_name}: {_prepare_value(value)}")
    return "{ " + ", ".join(items) + " }"

def _log_query(query: str, result: Any = None) -> None:
    """Log query and result if debug is enabled"""
    config = SurranticConfig.get_instance()
    if config.debug:
        logger.debug("Query: %s", query)
        if result is not None:
            logger.debug("Result: %s", result)

class SurranticConfig:
    """Configuration class for Surrantic database connection.
    
    This class allows overriding the default database configuration that would
    otherwise be loaded from environment variables.
    """
    _instance = None
    
    def __init__(self):
        self.address = SURREAL_ADDRESS
        self.user = SURREAL_USER
        self.password = SURREAL_PASS
        self.namespace = SURREAL_NAMESPACE
        self.database = SURREAL_DATABASE
        self.debug = False
    
    @classmethod
    def get_instance(cls) -> 'SurranticConfig':
        """Get the singleton instance of SurranticConfig"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def configure(cls, 
                 address: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 namespace: Optional[str] = None,
                 database: Optional[str] = None,
                 debug: Optional[bool] = None) -> None:
        """Configure the database connection parameters.
        
        Args:
            address: The SurrealDB server address
            user: The username for authentication
            password: The password for authentication
            namespace: The namespace to use
            database: The database to use
            debug: If True, all queries and results will be logged
        """
        config = cls.get_instance()
        if address is not None:
            config.address = address
        if user is not None:
            config.user = user
        if password is not None:
            config.password = password
        if namespace is not None:
            config.namespace = namespace
        if database is not None:
            config.database = database
        if debug is not None:
            config.debug = debug

class ObjectModel(BaseModel):
    """Base model class for SurrealDB objects with CRUD operations.
    
    This class provides both synchronous and asynchronous methods for interacting
    with SurrealDB, including save, get, get_all, and delete operations.

    Attributes:
        id: Optional record ID from SurrealDB
        table_name: Class variable defining the table name in SurrealDB
        created: Optional creation timestamp
        updated: Optional last update timestamp
    """
    id: Optional[RecordID] = None
    table_name: ClassVar[str] = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @field_serializer('id')
    def serialize_id(self, value: Optional[RecordID]) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _format_datetime_z(dt: datetime) -> str:
        """Format datetime in ISO format with Z instead of +00:00.
        
        Args:
            dt: The datetime object to format
            
        Returns:
            The formatted datetime string
        """
        return dt.isoformat().replace('+00:00', 'Z')

    @classmethod
    @asynccontextmanager
    async def _get_db(cls) -> AsyncGenerator[AsyncSurrealDB, None]:
        """Get a configured database connection as a context manager.
        
        Yields:
            AsyncSurrealDB: The configured database connection
        """
        config = SurranticConfig.get_instance()
        db = AsyncSurrealDB(url=config.address)
        try:
            await db.connect()
            await db.sign_in(config.user, config.password)
            await db.use(config.namespace, config.database)
            logger.debug("Database connection established")
            yield db
        finally:
            await db.close()
            logger.debug("Database connection closed")

    @classmethod
    @contextmanager
    def _get_sync_db(cls) -> Generator[SurrealDB, None, None]:
        """Get a configured synchronous database connection as a context manager.
        
        Yields:
            SurrealDB: The configured database connection
        """
        config = SurranticConfig.get_instance()
        db = SurrealDB(url=config.address)
        try:
            db.connect()
            db.sign_in(config.user, config.password)
            db.use(config.namespace, config.database)
            logger.debug("Database connection established")
            yield db
        finally:
            db.close()
            logger.debug("Database connection closed")

    @classmethod
    async def aget_all(cls: Type[T], order_by: Optional[str] = None, order_direction: Optional[str] = None) -> List[T]:
        """Asynchronously retrieve all records from the table.
        
        Args:
            order_by: Optional field name to order results by
            order_direction: Optional direction ('ASC' or 'DESC') for ordering
            
        Returns:
            List of model instances
            
        Raises:
            ValueError: If table_name is not set
            RuntimeError: If the database operation fails
        """
        if not cls.table_name:
            raise ValueError("table_name must be set")
        
        query = f"SELECT * FROM {cls.table_name}"
        if order_by:
            direction = order_direction or "ASC"
            query += f" ORDER BY {order_by} {direction}"
            
        _log_query(query)
        async with cls._get_db() as db:
            result = await db.query(query)
            _log_query(query, result)
            return [cls(**item) for item in result[0]["result"]]

    @classmethod
    def get_all(cls: Type[T], order_by: Optional[str] = None, order_direction: Optional[str] = None) -> List[T]:
        """Synchronously retrieve all records from the table.
        
        Args:
            order_by: Optional field name to order results by
            order_direction: Optional direction ('ASC' or 'DESC') for ordering
            
        Returns:
            List of model instances
            
        Raises:
            ValueError: If table_name is not set
            RuntimeError: If the database operation fails
        """
        if not cls.table_name:
            raise ValueError("table_name must be set")
        
        query = f"SELECT * FROM {cls.table_name}"
        if order_by:
            direction = order_direction or "ASC"
            query += f" ORDER BY {order_by} {direction}"
            
        _log_query(query)
        with cls._get_sync_db() as db:
            result = db.query(query)
            _log_query(query, result)
            return [cls(**item) for item in result[0]["result"]]

    @classmethod
    async def aget(cls: Type[T], id: Union[str, RecordID]) -> Optional[T]:
        """Asynchronously retrieve a single record by ID.
        
        Args:
            id: The record ID to retrieve, either as string or RecordID
            
        Returns:
            Model instance if found, None otherwise
            
        Raises:
            RuntimeError: If the database operation fails
        """
        query = f"SELECT * FROM {id}"
        _log_query(query)
        async with cls._get_db() as db:
            result = await db.query(query)
            _log_query(query, result)
            if result and result[0]:
                return cls(**result[0][0])
        return None

    @classmethod
    def get(cls: Type[T], id: Union[str, RecordID]) -> Optional[T]:
        """Synchronously retrieve a single record by ID.
        
        Args:
            id: The record ID to retrieve, either as string or RecordID
            
        Returns:
            Model instance if found, None otherwise
            
        Raises:
            RuntimeError: If the database operation fails
        """
        query = f"SELECT * FROM {id}"
        _log_query(query)
        with cls._get_sync_db() as db:
            result = db.query(query)
            _log_query(query, result)
            if result and result[0]:
                return cls(**result[0][0])
        return None

    async def asave(self) -> None:
        """Asynchronously save or update the record in SurrealDB.
        
        Updates the created and updated timestamps automatically.
        Creates a new record if id is None, otherwise updates existing record.
        
        Raises:
            Exception: If table_name is not defined
            RuntimeError: If the database operation fails
        """
        if not self.table_name:
            raise ValueError("table_name must be set")

        now = datetime.now(timezone.utc)
        if not self.created:
            self.created = now
        self.updated = now

        data = _prepare_data(self)
        if self.id:
            query = f"UPDATE {self.id} SET {data}"
        else:
            query = f"CREATE {self.table_name} SET {data}"

        _log_query(query)
        async with self._get_db() as db:
            result = await db.query(query)
            _log_query(query, result)
            if result and result[0]:
                self.id = RecordID.from_string(result[0][0]["id"])

    def save(self) -> None:
        """Synchronously save or update the record in SurrealDB.
        
        Updates the created and updated timestamps automatically.
        Creates a new record if id is None, otherwise updates existing record.
        
        Raises:
            Exception: If table_name is not defined
            RuntimeError: If the database operation fails
        """
        if not self.table_name:
            raise ValueError("table_name must be set")

        now = datetime.now(timezone.utc)
        if not self.created:
            self.created = now
        self.updated = now

        data = _prepare_data(self)
        if self.id:
            query = f"UPDATE {self.id} SET {data}"
        else:
            query = f"CREATE {self.table_name} SET {data}"

        _log_query(query)
        with self._get_sync_db() as db:
            result = db.query(query)
            _log_query(query, result)
            if result and result[0]:
                self.id = RecordID.from_string(result[0][0]["id"])

    async def adelete(self) -> None:
        """Asynchronously delete the record from the database.
        
        Raises:
            ValueError: If the record has no ID
            RuntimeError: If the database operation fails
        """
        if not self.id:
            raise ValueError("Cannot delete record without ID")

        query = f"DELETE {self.id}"
        _log_query(query)
        async with self._get_db() as db:
            result = await db.query(query)
            _log_query(query, result)

    def delete(self) -> None:
        """Synchronously delete the record from the database.
        
        Raises:
            ValueError: If the record has no ID
            RuntimeError: If the database operation fails
        """
        if not self.id:
            raise ValueError("Cannot delete record without ID")

        query = f"DELETE {self.id}"
        _log_query(query)
        with self._get_sync_db() as db:
            result = db.query(query)
            _log_query(query, result)