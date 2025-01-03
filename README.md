# Surrantic

A simple and intuitive Pydantic-based ORM for SurrealDB, providing both synchronous and asynchronous operations.

## Features

- 🔄 Both synchronous and asynchronous operations
- 🏗️ Built on top of Pydantic for robust data validation
- 🚀 Simple and intuitive API
- 📝 Type hints and comprehensive documentation
- 🔍 Automatic timestamp handling for created/updated fields
- 🎯 Support for complex queries and relationships

## Installation

```bash
pip install surrantic
```

## Quick Start

```python
from datetime import datetime
from typing import Optional
from surrantic import ObjectModel
from surrealdb import RecordID

class User(ObjectModel):
    table_name = "user"  # Define the table name in SurrealDB
    name: str
    email: str
    age: Optional[int] = None

# Async Usage
async def main():
    # Create a new user
    user = User(name="John Doe", email="john@example.com", age=30)
    await user.asave()  # Saves to SurrealDB
    print(f"User created with ID: {user.id}")

    # Fetch all users
    all_users = await User.aget_all()
    for user in all_users:
        print(f"Found user: {user.name}")

    # Get a specific user
    user_id = "user:123"  # or RecordID object
    user = await User.aget(user_id)
    if user:
        print(f"Found user: {user.name}")

    # Delete a user
    await user.adelete()

# Synchronous Usage
def sync_example():
    user = User(name="Jane Doe", email="jane@example.com")
    user.save()  # Synchronous save
    
    # Get all users
    users = User.get_all()
    
    # Delete user
    user.delete()
```

## Advanced Usage

### Custom Queries and Ordering

```python
# Get all users ordered by name
users = await User.aget_all(order_by="name", order_direction="ASC")
```

### Timestamps

Created and updated timestamps are automatically handled:

```python
user = User(name="John", email="john@example.com")
await user.asave()
print(f"Created at: {user.created}")  # Automatically set
print(f"Updated at: {user.updated}")  # Automatically set
```

### RecordID Serialization

When using `RecordID` fields in your models, you should add a field serializer to properly convert them to strings when using `model_dump()`. Here's an example:

```python
from pydantic import field_serializer
from surrealdb import RecordID

class User(ObjectModel):
    table_name = "user"
    name: str

class Post(ObjectModel):
    table_name = "post"
    title: str
    author: RecordID  # Reference to a User

    @field_serializer('author')
    def serialize_author(self, author: RecordID) -> str:
        return str(author)
```

Note: The base `ObjectModel` already handles the serialization of the `id` field.

## Configuration

### Database Connection

By default, Surrantic uses environment variables for database configuration:

```bash
SURREAL_ADDRESS=ws://localhost:8000
SURREAL_USER=root
SURREAL_PASS=root
SURREAL_NAMESPACE=test
SURREAL_DATABASE=test
```

You can also override these settings directly in your code using `SurranticConfig`:

```python
from surrantic import SurranticConfig

# Override all or some of the connection settings
SurranticConfig.configure(
    address="ws://mydb:8000",
    user="myuser",
    password="mypass",
    namespace="myns",
    database="mydb"
)

# Your models will now use the new configuration
user = User(name="John", email="john@example.com")
await user.asave()  # Uses the custom configuration
```

### Logging

Surrantic includes configurable logging:

```python
from surrantic.logging_config import setup_logging
import logging

# Console only logging
setup_logging(level=logging.DEBUG)

# Console and file logging
setup_logging(level=logging.INFO, log_file="surrantic.log")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Requirements

- Python 3.11+
- pydantic >= 2.0.0
- surrealdb >= 0.3.0

## Acknowledgments

- Built with [Pydantic](https://docs.pydantic.dev/)
- Powered by [SurrealDB](https://surrealdb.com/)
