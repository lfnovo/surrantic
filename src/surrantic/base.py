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

def _prepare_data(obj: Any) -> str:
    """Prepare data for database query."""
    items = []
    for field_name in obj.model_fields:
        value = getattr(obj, field_name)
        if value is not None:
            items.append(f"{field_name} = {_prepare_value(value)}")
    return ", ".join(items)

def _log_query(query: str, result: Any = None) -> None:
    """Log a query and its result.

    Args:
        query: The query to log
        result: Optional result to log
    """
    logger.debug(f"Query: {query}")
    if result is not None:
        logger.debug(f"Result type: {type(result)}")
        logger.debug(f"Result: {result}")

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
            _log_query("Database connection established")
            yield db
        finally:
            _log_query("Database connection closed")
            await db.close()

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
            _log_query("Database connection established")
            yield db
        finally:
            _log_query("Database connection closed")
            db.close()

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
            if result and len(result) > 0 and 'result' in result[0] and len(result[0]['result']) > 0:
                items = []
                for item in result[0]['result']:
                    items.append(cls(**item))
                return items
            return []

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
            if result and len(result) > 0 and 'result' in result[0] and len(result[0]['result']) > 0:
                items = []
                for item in result[0]['result']:
                    items.append(cls(**item))
                return items
            return []

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
            if result and len(result) > 0 and 'result' in result[0] and len(result[0]['result']) > 0:
                item = result[0]['result'][0]
                return cls(**item)
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
            if result and len(result) > 0 and 'result' in result[0] and len(result[0]['result']) > 0:
                item = result[0]['result'][0]
                return cls(**item)
            return None

    async def asave(self) -> None:
        """Save the model asynchronously."""
        if not self.table_name:
            raise ValueError("table_name must be set")

        if not self.created:
            self.created = datetime.now(timezone.utc)
        self.updated = datetime.now(timezone.utc)
        if not self.created:
            self.created = self.updated

        data = _prepare_data(self)
        query = f"UPDATE {self.table_name} SET {data}"
        if self.id:
            # Extract just the record ID part without the table name
            record_id = str(self.id).split(":")[-1]
            query = f"UPDATE {self.table_name}:{record_id} SET {data}"
        else:
            query = f"CREATE {self.table_name} SET {data}"

        async with self._get_db() as db:
            result = await db.query(query)
            _log_query(query, result)
            if result and len(result) > 0 and 'result' in result[0]:
                result_data = result[0]['result']
                if isinstance(result_data, str):
                    # If the result is a string (record ID), use it directly
                    self.id = result_data
                elif isinstance(result_data, list) and len(result_data) > 0:
                    # If the result is a list with dictionary items
                    if isinstance(result_data[0], dict):
                        self.id = result_data[0]["id"]
                    else:
                        self.id = result_data[0]
            logger.debug(f"asave result: {result}")

    def save(self) -> None:
        """Synchronously save the model to the database."""
        if not self.table_name:
            raise ValueError("table_name must be set")

        if not self.created:
            self.created = datetime.now(timezone.utc)
        self.updated = datetime.now(timezone.utc)
        if not self.created:
            self.created = self.updated

        data = _prepare_data(self)
        query = f"UPDATE {self.table_name} SET {data}"
        if self.id:
            # Extract just the record ID part without the table name
            record_id = str(self.id).split(":")[-1]
            query = f"UPDATE {self.table_name}:{record_id} SET {data}"
        else:
            query = f"CREATE {self.table_name} SET {data}"

        with self._get_sync_db() as db:
            result = db.query(query)
            _log_query(query, result)
            if result and len(result) > 0 and 'result' in result[0]:
                result_data = result[0]['result']
                if isinstance(result_data, str):
                    # If the result is a string (record ID), use it directly
                    self.id = result_data
                elif isinstance(result_data, list) and len(result_data) > 0:
                    # If the result is a list with dictionary items
                    if isinstance(result_data[0], dict):
                        self.id = result_data[0]["id"]
                    else:
                        self.id = result_data[0]

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