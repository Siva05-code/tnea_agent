import os
import asyncio
from datetime import datetime, timedelta

# MUST LOAD ENV VARS FIRST before any agent imports
from dotenv import load_dotenv
load_dotenv()

from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.tools import (
    database_introspection_tool,
    sql_generation_tool,
    sql_execution_tool,
)

# Initialize FastAPI app
app = FastAPI(
    title="TNEA College Assistant API",
    description="AI-powered college counselling agent",
    version="1.0.0"
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class QueryRequest(BaseModel):
    """User question request"""
    question: str = Field(..., description="Natural language question about colleges")
    limit: Optional[int] = Field(50, description="Maximum results to return")


class QueryResponse(BaseModel):
    """Query result response"""
    success: bool
    question: str
    generated_sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    error: Optional[str] = None
    timestamp: str


class SchemaResponse(BaseModel):
    """Database schema response"""
    database: str
    tables: List[Dict[str, Any]]
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: Optional[str] = None
    error: Optional[str] = None


class DirectSQLRequest(BaseModel):
    """Direct SQL execution request"""
    query: str = Field(..., description="SELECT query to execute")

# Global cache for schema
_schema_cache = None
_schema_cache_time = None
SCHEMA_CACHE_TTL = 3600  # 1 hour

async def get_cached_schema():
    """Get schema from cache or fetch it"""
    global _schema_cache, _schema_cache_time
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    # Check cache
    if _schema_cache and _schema_cache_time:
        elapsed = (datetime.now() - _schema_cache_time).total_seconds()
        if elapsed < SCHEMA_CACHE_TTL:
            return _schema_cache
    
    # Fetch fresh schema
    try:
        schema = await database_introspection_tool(db_url)
        _schema_cache = schema
        _schema_cache_time = datetime.now()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch schema: {str(e)}")

def validate_question(question: str) -> bool:
    """Validate that question is not empty"""
    if not question or len(question.strip()) < 3:
        raise ValueError("Question is too short. Please ask something specific.")
    
    return True

def convert_nl_to_sql(question: str, schema_context: str) -> str:
    """
    Convert natural language question to SQL using Groq LLM.
    """
    
    # Validate question
    validate_question(question)
    
    from groq import Groq
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    client = Groq(api_key=api_key)
    
    message = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""You are an SQL expert for PostgreSQL. Convert the natural language question to a PostgreSQL SELECT query.

DATABASE SCHEMA:
{schema_context}

RULES:
1. ONLY generate SELECT queries - no INSERT, UPDATE, DELETE, CREATE, DROP
2. Always add LIMIT clause
3. Use WHERE clauses only if the question mentions specific filters
4. Return ONLY the SQL query, no explanations or descriptions
5. All table and column names MUST exist in schema above
6. Use lowercase for table and column names

EXAMPLES:
- Q: "colleges in coimbatore" → SELECT college_code, college_name, location FROM colleges WHERE location ILIKE '%coimbatore%' LIMIT 50;
- Q: "list all branches" → SELECT branch_code, branch_name, category FROM branch LIMIT 50;
- Q: "candidates with rank over 1000" → SELECT * FROM candidate_allotment WHERE general_rank > 1000 LIMIT 50;

QUESTION: {question}

SQL QUERY:"""
            }
        ]
    )
    
    sql = message.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    if sql.startswith("```"):
        sql = sql.split("```", 1)[1].strip()
        if sql.endswith("```"):
            sql = sql.rsplit("```", 1)[0].strip()
        if sql.startswith("sql"):
            sql = sql[3:].strip()
    return sql



@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        return HealthResponse(
            status="unhealthy",
            error="DATABASE_URL not configured"
        )
    
    try:
        # Try to get schema to verify DB connection
        schema = await get_cached_schema()
        return HealthResponse(
            status="healthy",
            database=schema.database
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            error=str(e)
        )

@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    """Get database schema"""
    schema = await get_cached_schema()
    
    tables_data = [
        {
            "name": t.table_name,
            "columns": [
                {
                    "name": c.column_name,
                    "type": c.data_type,
                    "nullable": c.is_nullable == "YES",
                    "primary_key": c.is_primary_key
                }
                for c in t.columns
            ],
            "row_count": t.row_count
        }
        for t in schema.tables
    ]
    
    return SchemaResponse(
        database=schema.database,
        tables=tables_data,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """
    Main endpoint: Accept question and return results
    
    Args:
        request: QueryRequest with question and optional limit
        
    Returns:
        QueryResponse with results or error
    """
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        # Step 1: Get schema
        print(f"📚 Getting schema...")
        schema = await get_cached_schema()
        
        # Build schema context
        schema_context = "DATABASE SCHEMA:\n\n"
        for table in schema.tables:
            schema_context += f"TABLE: {table.table_name}\n"
            for col in table.columns:
                pk = " [PRIMARY KEY]" if col.is_primary_key else ""
                nullable = "" if col.is_nullable == "YES" else " [NOT NULL]"
                schema_context += f"  - {col.column_name}: {col.data_type}{pk}{nullable}\n"
            schema_context += "\n"
        
        # Step 2: Generate SQL from natural language
        print(f"🔍 Converting question to SQL: {request.question}")
        sql_query = convert_nl_to_sql(request.question, schema_context)
        
        # Enforce limit
        if request.limit and "LIMIT" not in sql_query.upper():
            sql_query += f" LIMIT {request.limit}"
        elif request.limit and "LIMIT" in sql_query.upper():
            # Replace existing LIMIT if provided
            import re
            sql_query = re.sub(r"LIMIT \d+", f"LIMIT {request.limit}", sql_query)
        
        print(f"📝 Generated SQL: {sql_query}")
        
        # Step 3: Execute query
        print(f"⚡ Executing query...")
        result = await sql_execution_tool(sql_query, database_url=db_url)
        
        if not result["success"]:
            return QueryResponse(
                success=False,
                question=request.question,
                generated_sql=sql_query,
                error=result.get("error", "Query execution failed"),
                row_count=0,
                timestamp=datetime.now().isoformat()
            )
        
        # Step 4: Return results
        print(f"✅ Retrieved {result['rows_count']} rows")
        
        return QueryResponse(
            success=True,
            question=request.question,
            generated_sql=sql_query,
            results=result.get("data", []),
            row_count=result.get("rows_count", 0),
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return QueryResponse(
            success=False,
            question=request.question,
            error=str(e),
            row_count=0,
            timestamp=datetime.now().isoformat()
        )

@app.post("/api/execute-sql")
async def execute_sql(sql_query: str = Body(..., embed=False)):
    """
    Direct SQL execution endpoint (for advanced users)
    
    WARNING: Only allows SELECT queries
    """
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    # Validate query
    if not sql_query.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
    
    try:
        result = await sql_execution_tool(sql_query, database_url=db_url)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return {
            "success": True,
            "query": sql_query,
            "rows": result.get("data", []),
            "row_count": result.get("rows_count", 0),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "TNEA College Assistant API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /api/health",
            "schema": "GET /api/schema",
            "ask": "POST /api/ask",
            "execute_sql": "POST /api/execute-sql",
            "docs": "GET /docs",
            "openapi": "GET /openapi.json"
        }
    }

def main():
    """Run the FastAPI server"""
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"\n🚀 Starting TNEA College Assistant API")
    print(f"📍 Server: http://{host}:{port}")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"🔗 OpenAPI: http://localhost:{port}/openapi.json")
    print(f"\n")
    
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )

if __name__ == "__main__":
    main()
