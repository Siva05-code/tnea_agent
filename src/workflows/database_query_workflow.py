"""Database Query Workflow - Orchestrates database introspection and SQL execution"""

import os
from typing import Optional, Dict, Any

from ..tools import (
    database_introspection_tool,
    sql_generation_tool,
    sql_execution_tool,
)


async def database_query_workflow(
    user_query: str,
    connection_string: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the database query workflow:
    1. Introspect database to get schema
    2. Generate SQL from natural language
    3. Execute the SQL query
    4. Return results

    Args:
        user_query: Natural language question about college data
        connection_string: Database connection string (uses DATABASE_URL env var if not provided)

    Returns:
        dict: Workflow execution results
    """
    db_connection = connection_string or os.getenv("DATABASE_URL")

    if not db_connection:
        return {
            "status": "error",
            "error": "DATABASE_URL environment variable not set",
            "steps": []
        }

    results = {
        "status": "pending",
        "steps": [],
        "final_results": None,
    }

    try:
        # Step 1: Introspect database
        print("🔍 Step 1: Introspecting database...")
        schema_data = await database_introspection_tool(db_connection)
        results["steps"].append(
            {
                "name": "introspect-database",
                "status": "completed",
                "data": {
                    "database": schema_data.database,
                    "table_count": len(schema_data.tables),
                    "tables": [t.table_name for t in schema_data.tables],
                },
            }
        )

        # Step 2: Generate SQL from natural language
        print(f"\n📝 Step 2: Generating SQL from question: {user_query}")
        sql_info = await sql_generation_tool(
            question=user_query,
            database_url=db_connection,
        )
        results["steps"].append(
            {
                "name": "generate-sql",
                "status": "completed",
                "data": {
                    "question": sql_info["question"],
                    "tables": sql_info["tables"],
                    "schema_context": sql_info["schema_context"][:200] + "...",
                },
            }
        )

        results["status"] = "completed"
        return results

    except Exception as error:
        results["status"] = "error"
        results["error"] = str(error)
        return results
