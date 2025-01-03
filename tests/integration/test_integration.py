import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import Optional
from surrantic.base import ObjectModel, SurranticConfig, RecordID
from surrealdb import RecordID  # type: ignore


class Person(ObjectModel):
    """Example model class for integration testing."""
    table_name = "person"
    name: str
    age: int
    email: Optional[str] = None


@pytest.fixture(autouse=True)
def setup_db():
    """Configure database connection for integration tests."""
    SurranticConfig.configure(
        address="ws://localhost:8013",
        user="root",
        password="root",
        namespace="test",
        database="test"
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database():
    """Clean up the database before each test."""
    # Delete all records before the test
    async with Person._get_db() as db:
        await db.query("DELETE FROM person RETURN NONE")
        await db.query("SELECT * FROM person")  # Ensure deletion is complete
    yield
    # Delete all records after the test
    async with Person._get_db() as db:
        await db.query("DELETE FROM person RETURN NONE")
        await db.query("SELECT * FROM person")  # Ensure deletion is complete


@pytest.mark.integration
def test_sync_crud_operations():
    """Test synchronous CRUD operations with actual database."""
    # Create
    person = Person(name="John Doe", age=30, email="john@example.com")
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

    # Get all
    person1 = Person(name="Alice", age=25)
    person2 = Person(name="Bob", age=35)
    person1.save()
    person2.save()

    all_persons = Person.get_all()
    assert len(all_persons) == 2
    names = {p.name for p in all_persons}
    assert names == {"Alice", "Bob"}

    # Get all with ordering
    ordered_persons = Person.get_all(order_by="age", order_direction="DESC")
    assert ordered_persons[0].name == "Bob"
    assert ordered_persons[1].name == "Alice"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_crud_operations():
    """Test asynchronous CRUD operations with actual database."""
    # Create
    person = Person(name="John Doe", age=30, email="john@example.com")
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

    # Get all
    person1 = Person(name="Alice", age=25)
    person2 = Person(name="Bob", age=35)
    await person1.asave()
    await person2.asave()

    all_persons = await Person.aget_all()
    assert len(all_persons) == 2
    names = {p.name for p in all_persons}
    assert names == {"Alice", "Bob"}

    # Get all with ordering
    ordered_persons = await Person.aget_all(order_by="age", order_direction="DESC")
    assert ordered_persons[0].name == "Bob"
    assert ordered_persons[1].name == "Alice"
