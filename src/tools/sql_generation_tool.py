"""SQL generation tool - converts natural language to SQL"""

import os
from typing import Optional

import mysql.connector
from mysql.connector import MySQLConnection


async def create_database_connection(connection_string: str) -> MySQLConnection:
    """Create a MySQL connection"""
    return mysql.connector.connect(
        uri=connection_string,
        connection_timeout=30,
    )


async def execute_query(connection: MySQLConnection, query: str) -> list:
    """Execute a query and return results"""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()


def build_schema_text(columns: list) -> str:
    """Build a text representation of the database schema"""
    table_columns = {}

    for col in columns:
        table_name = col.get("table_name") or col.get("TABLE_NAME")
        if table_name not in table_columns:
            table_columns[table_name] = []
        table_columns[table_name].append(col)

    text = "DATABASE SCHEMA:\n\n"

    for table_name in sorted(table_columns.keys()):
        cols = table_columns[table_name]
        text += f"TABLE: {table_name}\n"

        for col in cols:
            col_name = col.get("column_name") or col.get("COLUMN_NAME")
            data_type = col.get("data_type") or col.get("DATA_TYPE")
            column_key = col.get("column_key") or col.get("COLUMN_KEY")
            is_nullable = col.get("is_nullable") or col.get("IS_NULLABLE")

            pk = " [PRIMARY KEY]" if column_key == "PRI" else ""
            nullable = "" if is_nullable == "YES" else " [NOT NULL]"

            text += f"  - {col_name}: {data_type}{pk}{nullable}\n"

        text += "\n"

    return text


async def sql_generation_tool(
    question: str,
    generate_only: bool = False,
    database_url: Optional[str] = None,
) -> dict:
    """
    Generate SQL SELECT queries from natural language questions.
    First introspects database schema, then generates appropriate SQL.

    Args:
        question: Natural language question about colleges and admissions
        generate_only: If True, only generate SQL without executing
        database_url: Database connection URL (uses DATABASE_URL env var if not provided)

    Returns:
        dict: Generated SQL and schema information
    """
    db_url = database_url or os.getenv("DATABASE_URL")

    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")

    connection: Optional[MySQLConnection] = None

    try:
        print(f'📝 Processing question: "{question}"\n')

        connection = await create_database_connection(db_url)

        # Get database name
        db_result = await execute_query(connection, "SELECT DATABASE() as db_name")
        current_db = db_result[0]["db_name"] if db_result else None
        print(f"📊 Database: {current_db}\n")

        # Get table information
        tables_result = await execute_query(
            connection,
            """
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME
            """,
        )

        table_names = [t["TABLE_NAME"] for t in tables_result]
        print(f"📋 Available tables: {', '.join(table_names)}\n")

        # Get columns information
        columns_result = await execute_query(
            connection,
            """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY, IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
        )

        # Build schema context
        schema_context = build_schema_text(columns_result)

        return {
            "success": True,
            "question": question,
            "database": current_db,
            "tables": table_names,
            "schema_context": schema_context,
            "generate_only": generate_only,
            "nextInstruction": "Now use sql-execution tool to execute the query. The LLM should generate a SELECT query based on the schema context.",
        }

    except Exception as error:
        raise RuntimeError(f"Failed to generate SQL: {str(error)}") from error
    finally:
        if connection:
            connection.close()
