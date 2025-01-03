import pytest
from datetime import datetime, timezone
from typing import Generator, Optional, Union
from unittest.mock import AsyncMock, MagicMock, patch
from surrealdb import RecordID  # type: ignore

from surrantic.base import ObjectModel

# Test model class
class TestModel(ObjectModel):
    table_name = "test_table"
    id: Optional[Union[str, RecordID]] = None
    name: str
    age: int

@pytest.fixture
def test_model() -> TestModel:
    return TestModel(name="Test", age=25)

@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch('surrantic.base.SurrealDB') as mock:
        db_instance = MagicMock()
        mock.return_value = db_instance
        yield db_instance

@pytest.fixture
def mock_async_db() -> Generator[AsyncMock, None, None]:
    with patch('surrantic.base.AsyncSurrealDB') as mock:
        db_instance = AsyncMock()
        mock.return_value = db_instance
        yield db_instance

def test_prepare_value_datetime() -> None:
    dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    from surrantic.base import _prepare_value
    assert _prepare_value(dt) == "'2023-01-01T00:00:00+00:00'"

def test_prepare_value_record_id() -> None:
    record_id = RecordID("test_table", "123")
    from surrantic.base import _prepare_value
    assert _prepare_value(record_id) == str(record_id)

def test_prepare_value_regular() -> None:
    from surrantic.base import _prepare_value
    assert _prepare_value("test") == '"test"'
    assert _prepare_value(123) == '123'
    assert _prepare_value(True) == 'true'

def test_prepare_data() -> None:
    model = TestModel(name="Test", age=25)
    from surrantic.base import _prepare_data
    data = _prepare_data(model)
    assert 'name = "Test"' in data
    assert 'age = 25' in data

def test_format_datetime_z() -> None:
    dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    formatted = TestModel._format_datetime_z(dt)
    assert formatted.endswith('Z')
    assert '+00:00' not in formatted

def test_save_without_table_name() -> None:
    class InvalidModel(ObjectModel):
        name: str

    model = InvalidModel(name="Test")
    with pytest.raises(ValueError, match="table_name must be set"):
        model.save()

def test_save_success(mock_db: MagicMock, test_model: TestModel) -> None:
    record_id = RecordID("test_table", "123")
    mock_db.query.return_value = [{"result": [{"id": str(record_id)}]}]
    
    test_model.save()
    
    assert test_model.id == str(record_id)
    assert test_model.created is not None
    assert test_model.updated is not None
    mock_db.query.assert_called_once()

@pytest.mark.asyncio
async def test_asave_success(mock_async_db: AsyncMock, test_model: TestModel) -> None:
    record_id = RecordID("test_table", "123")
    mock_async_db.query.return_value = [{"result": [{"id": str(record_id)}]}]
    
    await test_model.asave()
    
    assert test_model.id == str(record_id)
    assert test_model.created is not None
    assert test_model.updated is not None
    mock_async_db.query.assert_called_once()

def test_get_all_no_table_name() -> None:
    class InvalidModel(ObjectModel):
        name: str

    with pytest.raises(ValueError, match="table_name must be set"):
        InvalidModel.get_all()

@pytest.mark.asyncio
async def test_aget_all_success(mock_async_db: AsyncMock) -> None:
    id1 = RecordID("test_table", "1")
    id2 = RecordID("test_table", "2")
    mock_async_db.query.return_value = [{"result": [
        {"id": str(id1), "name": "Test1", "age": 25},
        {"id": str(id2), "name": "Test2", "age": 30}
    ]}]
    
    results = await TestModel.aget_all()
    
    assert len(results) == 2
    assert all(isinstance(r, TestModel) for r in results)
    assert results[0].name == "Test1"
    assert results[1].age == 30

def test_get_all_success(mock_db: MagicMock) -> None:
    id1 = RecordID("test_table", "1")
    id2 = RecordID("test_table", "2")
    mock_db.query.return_value = [{"result": [
        {"id": str(id1), "name": "Test1", "age": 25},
        {"id": str(id2), "name": "Test2", "age": 30}
    ]}]
    
    results = TestModel.get_all()
    
    assert len(results) == 2
    assert all(isinstance(r, TestModel) for r in results)
    assert results[0].name == "Test1"
    assert results[1].age == 30

def test_get_success(mock_db: MagicMock) -> None:
    record_id = RecordID("test_table", "1")
    mock_db.query.return_value = [{"result": [{"id": str(record_id), "name": "Test1", "age": 25}]}]
    
    result = TestModel.get(record_id)
    
    assert isinstance(result, TestModel)
    assert result.name == "Test1"
    assert result.age == 25

@pytest.mark.asyncio
async def test_aget_success(mock_async_db: AsyncMock) -> None:
    record_id = RecordID("test_table", "1")
    mock_async_db.query.return_value = [{"result": [{"id": str(record_id), "name": "Test1", "age": 25}]}]
    
    result = await TestModel.aget(record_id)
    
    assert isinstance(result, TestModel)
    assert result.name == "Test1"
    assert result.age == 25

def test_get_not_found(mock_db: MagicMock) -> None:
    mock_db.query.return_value = [{"result": []}]
    
    result = TestModel.get(RecordID("test_table", "1"))
    
    assert result is None

@pytest.mark.asyncio
async def test_aget_not_found(mock_async_db: AsyncMock) -> None:
    mock_async_db.query.return_value = [{"result": []}]
    
    result = await TestModel.aget(RecordID("test_table", "1"))
    
    assert result is None

def test_delete_no_id(test_model: TestModel) -> None:
    with pytest.raises(ValueError, match="Cannot delete record without ID"):
        test_model.delete()

@pytest.mark.asyncio
async def test_adelete_success(mock_async_db: AsyncMock, test_model: TestModel) -> None:
    test_model.id = RecordID("test_table", "123")
    mock_async_db.query.return_value = [{"result": []}]
    
    await test_model.adelete()
    
    mock_async_db.query.assert_called_once()

def test_delete_success(mock_db: MagicMock, test_model: TestModel) -> None:
    test_model.id = RecordID("test_table", "123")
    mock_db.query.return_value = [{"result": []}]
    
    test_model.delete()
    
    mock_db.query.assert_called_once()

def test_get_all_with_ordering(mock_db: MagicMock) -> None:
    mock_db.query.return_value = [{"result": []}]
    
    TestModel.get_all(order_by="name", order_direction="ASC")
    
    mock_db.query.assert_called_once()

@pytest.mark.asyncio
async def test_aget_all_with_ordering(mock_async_db: AsyncMock) -> None:
    mock_async_db.query.return_value = [{"result": []}]
    
    await TestModel.aget_all(order_by="name", order_direction="DESC")
    
    mock_async_db.query.assert_called_once()

def test_surrantic_config_singleton():
    from surrantic.base import SurranticConfig
    
    config1 = SurranticConfig.get_instance()
    config2 = SurranticConfig.get_instance()
    
    assert config1 is config2

def test_surrantic_config_default_values():
    from surrantic.base import SurranticConfig, SURREAL_ADDRESS, SURREAL_USER, SURREAL_PASS, SURREAL_NAMESPACE, SURREAL_DATABASE
    
    # Reset to default values
    SurranticConfig.reset()
    config = SurranticConfig.get_instance()
    
    assert config.address == SURREAL_ADDRESS
    assert config.user == SURREAL_USER
    assert config.password == SURREAL_PASS
    assert config.namespace == SURREAL_NAMESPACE
    assert config.database == SURREAL_DATABASE

def test_surrantic_config_override():
    from surrantic.base import SurranticConfig
    
    # Store original values
    config = SurranticConfig.get_instance()
    original_address = config.address
    original_user = config.user
    
    # Override some values
    SurranticConfig.configure(
        address="ws://testdb:8000",
        user="testuser"
    )
    
    # Check overridden values
    assert config.address == "ws://testdb:8000"
    assert config.user == "testuser"
    
    # Check non-overridden values remain the same
    assert config.password == original_user
    
    # Reset for other tests
    SurranticConfig.configure(
        address=original_address,
        user=original_user
    )

@pytest.mark.asyncio
async def test_db_connection_uses_config(mock_async_db: AsyncMock):
    from surrantic.base import SurranticConfig
    
    # Configure custom connection details
    SurranticConfig.configure(
        address="ws://testdb:8000",
        user="testuser",
        password="testpass",
        namespace="testns",
        database="testdb"
    )
    
    # Set up mock response
    record_id = RecordID("test_table", "123")
    mock_async_db.query.return_value = [{"result": [{"id": str(record_id)}]}]
    
    model = TestModel(name="Test", age=25)
    await model.asave()
    
    # Verify the connection was made with our custom config
    mock_async_db.connect.assert_called_once()
    mock_async_db.sign_in.assert_called_once_with("testuser", "testpass")
    mock_async_db.use.assert_called_once_with("testns", "testdb")
