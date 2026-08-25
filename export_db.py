"""
export_db.py

Script to read DATABASE_URL from local .env, connect to PostgreSQL (or configured database),
query all tables, and export the data into database_backup.json with proper datetime handling.
"""

import os
import sys
import json
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from uuid import UUID
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy import create_engine, inspect, text


def json_serializer(obj):
    """
    Custom JSON serializer function to handle datetime, date, time, timedelta,
    UUID, Decimal, bytes, and set objects.
    """
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    elif isinstance(obj, timedelta):
        return str(obj)
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            import base64
            return base64.b64encode(obj).decode("utf-8")
    elif isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def export_database(env_path: str = ".env", output_file: str = "database_backup.json"):
    """
    Reads DATABASE_URL from env_path, connects to the database, queries all tables,
    and writes table contents to output_file in JSON format.
    """
    # 1. Load environment variables from .env file
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from '{env_path}'")
    else:
        print(f"Warning: '{env_path}' file not found. Reading from environment variables.")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env or environment variables.", file=sys.stderr)
        sys.exit(1)

    print(f"DATABASE_URL found.")

    # Normalize PostgreSQL URL scheme if needed
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    elif db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

    # 2. Create engine and test connection
    try:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        engine = create_engine(db_url, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Successfully connected to the database.")
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Inspect tables and query all data
    inspector = inspect(engine)
    try:
        tables = inspector.get_table_names()
    except Exception as e:
        print(f"Error inspecting database tables: {e}", file=sys.stderr)
        sys.exit(1)

    if not tables:
        print("No tables found in the database.")

    backup_data = {
        "exported_at": datetime.now().isoformat(),
        "total_tables": len(tables),
        "tables": {}
    }

    print(f"Found {len(tables)} table(s) to export:")

    with engine.connect() as conn:
        for table in sorted(tables):
            try:
                result = conn.execute(text(f'SELECT * FROM "{table}"'))
                rows = [dict(row) for row in result.mappings()]
                backup_data["tables"][table] = rows
                print(f"  - Table '{table}': {len(rows)} record(s) exported")
            except Exception as e:
                print(f"  - Table '{table}': failed to export ({e})", file=sys.stderr)

    # 4. Save to backup file
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        print(f"\nDatabase backup successfully exported to '{output_file}'.")
    except Exception as e:
        print(f"Error saving backup file '{output_file}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    export_database()
