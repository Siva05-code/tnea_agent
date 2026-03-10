"""SQL execution tool - safely executes SQL queries with validation"""

import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor


# Allowed SQL functions for security
ALLOWED_FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "upper",
    "lower",
    "length",
    "substring",
    "date_part",
    "now",
    "current_timestamp",
    "current_date",
    "coalesce",
    "greatest",
    "least",
}


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


def sanitize_query_for_pattern_matching(query: str) -> str:
    """
    Sanitize SQL query by removing string literals and comments before pattern matching.
    This prevents false positives from dangerous patterns appearing in string literals.
    """
    sanitized = query

    # Remove single-quoted string literals (handle escaped quotes)
    sanitized = re.sub(r"'(?:''|[^'])*'", "''", sanitized)

    # Remove double-quoted identifiers (handle escaped quotes)
    sanitized = re.sub(r'"(?:""|[^"])*"', '""', sanitized)

    # Remove multi-line /* */ comments
    sanitized = re.sub(r"/\*[\s\S]*?\*/", " ", sanitized)

    # Remove single-line -- comments
    sanitized = re.sub(r"--.*$", " ", sanitized, flags=re.MULTILINE)

    # Normalize whitespace
    sanitized = re.sub(r"\s+", " ", sanitized)

    return sanitized.lower()


def validate_query(query: str) -> None:
    """
    Validate that the query is safe to execute.

    Raises:
        ValueError: If the query is not safe
    """
    trimmed = query.strip()

    lines = trimmed.split('\n')
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        # Skip empty lines and comment lines
        if stripped_line and not stripped_line.startswith('--') and not stripped_line.startswith('#'):
            trimmed = '\n'.join(lines[i:])
            break
    
    trimmed_lower = trimmed.strip().lower()

    if not trimmed_lower.startswith("select"):
        raise ValueError("Only SELECT queries are allowed for security reasons")

    # Sanitize the query by removing string literals and comments
    normalized = sanitize_query_for_pattern_matching(query)

    # Block common dangerous patterns
    dangerous_patterns = [
        # PostgreSQL system functions and commands
        r"\bpg_\w+\s*\(",
        r"\bcopy\s+",
        r"\bcreate\s+",
        r"\bdrop\s+",
        r"\balter\s+",
        r"\btruncate\s+",
        r"\bdelete\s+",
        r"\bupdate\s+",
        r"\binsert\s+",
        # File operations
        r"\bload_file\s*\(",
        # Code evaluation and execution
        r"\beval\s*\(",
        r"\bexecute\s+",
        r"\bprepare\s+",
        # Time/resource manipulation
        r"\bpg_sleep\s*\(",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, normalized):
            raise ValueError(f"Dangerous SQL pattern detected: {pattern}")

    # Block multiple statements
    if ";" in query and not query.rstrip().endswith(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    if re.search(r"\bunion\s+", normalized):
        raise ValueError("UNION queries are not allowed")


async def sql_execution_tool(sql_query: str, database_url: Optional[str] = None) -> dict:
    """
    Execute a SQL SELECT query against the PostgreSQL database.

    Args:
        sql_query: SQL SELECT query to execute
        database_url: Database connection URL (uses DATABASE_URL env var if not provided)

    Returns:
        dict: Query results and execution metadata

    Raises:
        ValueError: If query is not safe
        RuntimeError: If execution fails
    """
    db_url = database_url or os.getenv("DATABASE_URL")

    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")

    # Validate query
    try:
        validate_query(sql_query)
    except ValueError as e:
        raise ValueError(f"Query validation failed: {str(e)}") from e

    connection = None

    try:
        print(f"📝 Executing SQL query...\n")

        # Parse connection string and create connection
        conn_params = parse_connection_string(db_url)
        
        connection = psycopg2.connect(
            host=conn_params["host"],
            port=conn_params["port"],
            user=conn_params["user"],
            password=conn_params["password"],
            database=conn_params["database"],
        )

        # Execute the query
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        cursor.close()

        # Convert to list of dicts
        data = [dict(row) for row in rows]

        return {
            "success": True,
            "database": conn_params["database"],
            "query": sql_query,
            "rows_count": len(data),
            "data": data,
        }

    except psycopg2.Error as error:
        raise RuntimeError(f"Failed to execute query: {str(error)}") from error
    finally:
        if connection:
            connection.close()
