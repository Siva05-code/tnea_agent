"""Database introspection tool - analyzes PostgreSQL database schema"""

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Info about a database column"""

    column_name: str
    data_type: str
    character_max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    is_nullable: str
    column_default: Optional[str] = None
    is_primary_key: bool = False


class TableInfo(BaseModel):
    """Info about a database table"""

    table_name: str
    columns: List[ColumnInfo]
    row_count: int = 0


class SchemaInfo(BaseModel):
    """Complete database schema information"""

    database: str
    tables: List[TableInfo]
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    indexes: List[Dict[str, Any]] = Field(default_factory=list)


def parse_connection_string(connection_string: str) -> Dict[str, str]:
    """Parse PostgreSQL connection string"""
    # Handle both postgresql:// and postgresql+psycopg://
    conn_str = connection_string.replace("postgresql+psycopg://", "postgresql://")
    
    parsed = urlparse(conn_str)
    
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "database": parsed.path.lstrip("/").split("?")[0] or "postgres",
    }


async def execute_query(connection, query: str) -> List[Dict[str, Any]]:
    """Execute a query and return results"""
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()


async def database_introspection_tool(connection_string: str) -> SchemaInfo:
    """
    Introspect a PostgreSQL database to understand its schema, tables, columns, and relationships

    Args:
        connection_string: PostgreSQL connection string

    Returns:
        SchemaInfo: Complete database schema information
    """
    connection = None

    try:
        print("🔌 Connecting to PostgreSQL for introspection...")
        
        # Parse connection string
        conn_params = parse_connection_string(connection_string)
        
        # Create connection
        connection = psycopg2.connect(
            host=conn_params["host"],
            port=conn_params["port"],
            user=conn_params["user"],
            password=conn_params["password"],
            database=conn_params["database"],
        )
        
        print("✅ Connected to PostgreSQL for introspection")
        
        current_db = conn_params["database"]

        # Get all tables (excluding system tables)
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        tables_result = cursor.fetchall()
        cursor.close()

        tables: List[TableInfo] = []

        for table_row in tables_result:
            table_name = table_row["table_name"]

            # Get columns for this table
            columns_query = """
            SELECT 
                columns.column_name,
                columns.data_type,
                columns.character_maximum_length as character_max_length,
                columns.numeric_precision,
                columns.numeric_scale,
                columns.is_nullable,
                columns.column_default,
                COALESCE(tc.is_primary_key, false) as is_primary_key
            FROM information_schema.columns
            LEFT JOIN (
                SELECT column_name, true as is_primary_key
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc 
                    ON kcu.constraint_name = tc.constraint_name 
                    AND kcu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND kcu.table_name = %s
                    AND kcu.table_schema = 'public'
            ) tc ON columns.column_name = tc.column_name
            WHERE columns.table_name = %s AND columns.table_schema = 'public'
            ORDER BY columns.ordinal_position
            """

            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(columns_query, (table_name, table_name))
            columns_result = cursor.fetchall()
            cursor.close()

            columns: List[ColumnInfo] = []

            for col in columns_result:
                columns.append(
                    ColumnInfo(
                        column_name=col["column_name"],
                        data_type=col["data_type"],
                        character_max_length=col.get("character_max_length"),
                        numeric_precision=col.get("numeric_precision"),
                        numeric_scale=col.get("numeric_scale"),
                        is_nullable=col["is_nullable"],
                        column_default=col.get("column_default"),
                        is_primary_key=col.get("is_primary_key", False),
                    )
                )

            # Get row count
            count_query = f"SELECT COUNT(*) as count FROM {table_name}"
            
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(count_query)
            count_result = cursor.fetchone()
            cursor.close()
            
            row_count = count_result["count"] if count_result else 0

            tables.append(
                TableInfo(
                    table_name=table_name,
                    columns=columns,
                    row_count=row_count,
                )
            )

        # Get foreign key relationships
        relationships_query = """
        SELECT 
            kcu.constraint_name,
            kcu.table_name,
            kcu.column_name,
            ccu.table_name as foreign_table_name,
            ccu.column_name as foreign_column_name
        FROM information_schema.key_column_usage kcu
        JOIN information_schema.constraint_column_usage ccu 
            ON kcu.constraint_name = ccu.constraint_name
            AND kcu.table_schema = ccu.table_schema
        WHERE kcu.table_schema = 'public'
        """
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(relationships_query)
        relationships_result = cursor.fetchall()
        cursor.close()

        relationships = [dict(rel) for rel in relationships_result]

        # Get indexes
        indexes_query = """
        SELECT 
            indexname as index_name,
            tablename as table_name,
            indexdef as definition
        FROM pg_indexes
        WHERE schemaname = 'public'
        """
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(indexes_query)
        indexes_result = cursor.fetchall()
        cursor.close()

        indexes = [dict(idx) for idx in indexes_result]

        return SchemaInfo(
            database=current_db,
            tables=tables,
            relationships=relationships,
            indexes=indexes,
        )

    except Exception as e:
        print(f"❌ Database introspection error: {e}")
        raise

    finally:
        if connection:
            connection.close()
