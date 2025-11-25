from alembic import context
from sqlalchemy import create_engine
from logging.config import fileConfig
from backend.db import Base, DATABASE_URL  # Import your Base and DB URL

# Alembic Config
config = context.config

# Replace alembic.ini URL with your real Railway URL
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret config file for Python logging
fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = create_engine(DATABASE_URL)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()
