import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from typing import Optional

from surrantic.base import SurranticConfig

# Configure database connection for integration tests
SurranticConfig.configure(
    address="ws://localhost:8013",
    user="root",
    password="root",
    namespace="test",
    database="test"
)

from surrantic.base import ObjectModel, RecordID
from surrealdb import RecordID  # type: ignore


class Person(ObjectModel):
    """Example model class for integration testing."""
    table_name = "person"
    name: str
    age: int
    email: Optional[str] = None
    birth_date: Optional[datetime] = None


@pytest.fixture(autouse=True)
def setup_db():
    """Configure database connection for integration tests."""
    pass


@pytest_asyncio.fixture(scope="function")
async def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database():
    """Clean up the database before each test."""
    # Delete all records before the test
    async with Person._get_db() as db:
        await db.query("DEFINE TABLE person")
    yield
    # Delete all records after the test
    async with Person._get_db() as db:
        await db.query("REMOVE TABLE person")


@pytest.mark.integration
def test_sync_crud_operations():
    """Test synchronous CRUD operations with actual database."""
    # Create
    person = Person(
        name="John Doe", 
        age=30, 
        email="john@example.com",
        birth_date=datetime(1993, 5, 15, tzinfo=timezone.utc)
    )
    person.save()
    assert person.id is not None
    assert isinstance(person.id, RecordID)
    assert person.created is not None
    assert person.updated is not None

    # Read
    record_id = person.id
    retrieved = Person.get(record_id)
    assert retrieved is not None
    assert retrieved.name == "John Doe"
    assert retrieved.age == 30
    assert retrieved.email == "john@example.com"
    assert retrieved.birth_date == datetime(1993, 5, 15, tzinfo=timezone.utc)

    # Update
    retrieved.name = "Jane Doe"
    retrieved.save()
    updated = Person.get(record_id)
    assert updated is not None
    assert updated.name == "Jane Doe"

    # Delete
    retrieved.delete()
    deleted = Person.get(record_id)
    assert deleted is None

    # Get all with datetime filtering
    person1 = Person(
        name="Alice", 
        age=25,
        birth_date=datetime(1998, 3, 20, tzinfo=timezone.utc)
    )
    person2 = Person(
        name="Bob", 
        age=35,
        birth_date=datetime(1988, 8, 10, tzinfo=timezone.utc)
    )
    person1.save()
    person2.save()

    # Test filtering by birth date
    query = "SELECT * FROM person WHERE birth_date > '1990-01-01T00:00:00Z'"
    with Person._get_sync_db() as db:
        result = db.query(query)
        assert len(result[0]['result']) == 1
        assert result[0]['result'][0]['name'] == "Alice"

    # Get all with ordering
    ordered_persons = Person.get_all(order_by="age", order_direction="DESC")
    assert ordered_persons[0].name == "Bob"
    assert ordered_persons[1].name == "Alice"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_crud_operations():
    """Test asynchronous CRUD operations with actual database."""
    # Create
    person = Person(
        name="John Doe", 
        age=30, 
        email="john@example.com",
        birth_date=datetime(1993, 5, 15, tzinfo=timezone.utc)
    )
    await person.asave()
    assert person.id is not None
    assert isinstance(person.id, RecordID)
    assert person.created is not None
    assert person.updated is not None

    # Read
    record_id = person.id
    retrieved = await Person.aget(record_id)
    assert retrieved is not None
    assert retrieved.name == "John Doe"
    assert retrieved.age == 30
    assert retrieved.email == "john@example.com"
    assert retrieved.birth_date == datetime(1993, 5, 15, tzinfo=timezone.utc)

    # Update
    retrieved.name = "Jane Doe"
    await retrieved.asave()
    updated = await Person.aget(record_id)
    assert updated is not None
    assert updated.name == "Jane Doe"

    # Delete
    await retrieved.adelete()
    deleted = await Person.aget(record_id)
    assert deleted is None

    # Get all with datetime filtering
    person1 = Person(
        name="Alice", 
        age=25,
        birth_date=datetime(1998, 3, 20, tzinfo=timezone.utc)
    )
    person2 = Person(
        name="Bob", 
        age=35,
        birth_date=datetime(1988, 8, 10, tzinfo=timezone.utc)
    )
    await person1.asave()
    await person2.asave()

    # Test filtering by birth date
    query = "SELECT * FROM person WHERE birth_date > '1990-01-01T00:00:00Z'"
    async with Person._get_db() as db:
        result = await db.query(query)
        assert len(result[0]['result']) == 1
        assert result[0]['result'][0]['name'] == "Alice"

    # Get all with ordering
    ordered_persons = await Person.aget_all(order_by="age", order_direction="DESC")
    assert ordered_persons[0].name == "Bob"
    assert ordered_persons[1].name == "Alice"
