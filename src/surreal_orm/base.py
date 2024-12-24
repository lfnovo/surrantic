import json
import logging
from datetime import datetime, timezone
from typing import Any, ClassVar, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from surrealdb import AsyncSurrealDB, RecordID  # type: ignore

T = TypeVar("T", bound="ObjectModel")

logger = logging.getLogger(__name__)

def _prepare_value(value: Any) -> str:
    """Convert Python value to SurrealQL value format"""
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

class ObjectModel(BaseModel):
    id: Optional[RecordID] = None
    table_name: ClassVar[str] = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @staticmethod
    def _format_datetime_z(dt: datetime) -> str:
        """Format datetime in ISO format with Z instead of +00:00"""
        return dt.isoformat().replace('+00:00', 'Z')

    async def asave(self) -> None:
        if not self.created:
            self.created = datetime.now(timezone.utc)  # Make created timezone-aware
        self.updated = datetime.now(timezone.utc)      # Make updated timezone-aware

        if type(self).table_name:
            table_name = type(self).table_name
        else:
            raise Exception("No table_name defined")
                
        data = _prepare_data(self)
        logger.debug("Prepared data for save: %s", data)

        async with AsyncSurrealDB(url="ws://localhost:8000") as db:
            await db.connect()
            await db.sign_in("root", "root")
            await db.use("namespace", "database_name")
            logger.info("Database connection established for save operation")
            result = await db.query(f"UPSERT {table_name} CONTENT {data}")
            await db.close()
        logger.debug("Save operation result: %s", result)
        self.id = result[0]["result"][0]["id"]
        logger.info("Successfully saved record with ID: %s", self.id)
    
    @classmethod
    async def aget_all(cls: Type[T], order_by: Optional[str] = None, order_direction: Optional[str] = None) -> List[T]:
        try:
            if cls.table_name:
                target_class = cls
                table_name = cls.table_name
            else:
                raise ValueError("table_name not set in model class")

            query = f"SELECT * FROM {table_name}"
            if order_by:
                query += f" ORDER BY {order_by} {order_direction}"

            async with AsyncSurrealDB(url="ws://localhost:8000") as db:
                await db.connect()
                await db.sign_in("root", "root")
                await db.use("namespace", "database_name")
                logger.info("Database connection established for fetch operation")
                results = await db.query(query)
                await db.close()
            logger.debug("Fetch all operation results: %s", results)
            return [target_class(**item) for item in results[0]["result"]]  
        except Exception as e: 
            logger.error("Failed to fetch records: %s", str(e), exc_info=True)
            raise RuntimeError(f"Failed to fetch records: {str(e)}")

    
    @classmethod
    async def aget(cls: Type[T], id: Union[ str, RecordID]) -> T:
        try:
            
            async with AsyncSurrealDB(url="ws://localhost:8000") as db:
                await db.connect()
                await db.sign_in("root", "root")
                await db.use("namespace", "database_name")
                logger.info("Database connection established for get operation")
                results = await db.select(id)
                await db.close()

            logger.debug("Get operation results: %s", results)
            return cls(**results)
        except Exception as e:
            logger.error("Failed to fetch record: %s", str(e), exc_info=True)
            raise RuntimeError(f"Failed to fetch record: {str(e)}")
    
    async def adelete(self) -> None:
        try:
            if not self.table_name:
                raise ValueError("table_name not set in model class")
            if not self.id:
                raise ValueError("Cannot delete record without id")

            async with AsyncSurrealDB(url="ws://localhost:8000") as db:
                await db.connect()
                await db.sign_in("root", "root")
                await db.use("namespace", "database_name")
                logger.info("Database connection established for delete operation")
                await db.delete(self.id)
                await db.close()
                logger.info("Successfully deleted record with ID: %s", self.id)
        except Exception as e:
            logger.error("Failed to delete record: %s", str(e), exc_info=True)
            raise RuntimeError(f"Failed to delete record: {str(e)}")