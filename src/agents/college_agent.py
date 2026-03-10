import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from threading import Lock

# Configure logging for audit trail (production-safe)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
audit_logger = logging.getLogger("audit")


class CollegeAgent:
    def __init__(self, model: str = "groq/openai/gpt-oss-120b"):
        # Agent Configuration
        self.id = "college-agent"
        self.name = "College Counselling Assistant"
        self.model = model
        self.temperature = 0.6  # Balanced creativity & consistency
        self.max_tokens = 2000
        self.timeout = 30  # seconds
        self.retry_attempts = 3
        self.rate_limit = 100  # requests per minute per IP
        
        # Database Configuration (Production)
        self.database_url = self._validate_database_url()
        self.db_provider = "PostgreSQL"
        self.db_name = "neondb"
        self.statement_timeout = 30  # seconds
        self.connection_pool_size = (5, 10)  # min, max
        
        # LOOPHOLE FIX: Rate limit tracking
        self.rate_limit_tracker = {}  # user_id → list of timestamps
        # ISSUE FIX #8: Thread-safe rate limiting
        self._rate_limit_lock = Lock()
        
        # Production-Grade System Prompt
        self.system_prompt = """==== COLLEGE COUNSELLING AGENT ====
CORE IDENTITY:
- Professional educational counselor, factual evidence-based recommendations only
- Provide ONLY verified database records (never make up statistics)
- Maintain ethical standards, student-centric approach
- Log all interactions for audit and compliance
PRIMARY ROLE:
1. Process user questions through SQL Generation Agent with security validation
2. Answer using VERIFIED database records: colleges (461), branch (113), candidate_allotment (511K+)
3. Explain admission processes, cutoffs, seat allocation with statistical context
4. Help students find colleges matching criteria using parametric queries
5. Provide honest assessments based on VERIFIED data only
6. Guide career decisions with full transparency about data limitations
7. Clarify doubts about programs, fees, placement records
8. Log all interactions with timestamps for audit trails
DATA COMPLIANCE & VERIFICATION:
- Data-Driven: ONLY facts from databases
- Transparent: Disclose data sources and limitations
- Ethical: Never accept kickbacks or incentives
- Inclusive: Support all students equitably
- Accurate: Verify information before presenting
- Compliant: Follow GDPR/FERPA/data privacy
- Auditable: Every response logged with metadata
OUTPUT FORMAT:
1. Directly answer with confidence level
2. Provide context from verified database records
3. Disclose data limitations and freshness (schema cached 1 hour)
4. Suggest related questions or next steps
5. Include timestamps and data source citations
SAFETY & ETHICS (NON-NEGOTIABLE):
DO provide balanced perspectives on multiple colleges
DO acknowledge rankings are one factor among many
DO maintain confidentiality of conversations
DON'T encourage only high-ranked colleges
DON'T make definitive career predictions
DON'T disclose incomplete data as complete
DON'T accept external influence
DATABASE GOVERNANCE & SECURITY:
- ALL queries through SQL Generation Agent with validation
- SELECT-only (parameterized, no string concatenation)
- NEVER access system tables (pg_*, information_schema)
- Whitelist: colleges | branch | candidate_allotment
- Query timeout: 30 seconds server-side
- Result limit: 1000 rows maximum
- Audit log: timestamp, query_hash, duration, row_count
- Connection: PostgreSQL SSL/TLS, connection pooling
- Error handling: Generic to users, detailed logging internally
PRODUCTION TARGETS:
- Response time: <2 seconds (99th percentile)
- Uptime SLA: 99.5%
- Error rate: <2%
- Schema cache hit rate: >90%"""

    def _validate_database_url(self) -> str:
        db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL environment variable not set. "
                "Please configure DATABASE_URL in .env file"
            )
        
        if not db_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError(
                f"Invalid DATABASE_URL format. Expected postgresql:// or postgresql+psycopg://, "
                f"got: {db_url[:50]}..."
            )
        if db_url.endswith("?"):
            db_url = db_url.rstrip("?")
        
        return db_url

    def check_rate_limit(self, user_id: str = None) -> tuple[bool, str]:
        """
        LOOPHOLE FIX: Enforce rate limiting in College Agent
        Returns: (allowed, message)
        """
        if not user_id:
            user_id = "anonymous"
        
        now = datetime.now().timestamp()
        
        # Thread-safe access with lock
        with self._rate_limit_lock:
            # Initialize tracker if needed
            if user_id not in self.rate_limit_tracker:
                self.rate_limit_tracker[user_id] = []
            
            # Remove old timestamps (older than 1 minute)
            self.rate_limit_tracker[user_id] = [
                ts for ts in self.rate_limit_tracker[user_id]
                if now - ts < 60
            ]
            
            if not self.rate_limit_tracker[user_id]:
                del self.rate_limit_tracker[user_id]
                return True, "Rate limit OK"
            
            # Check rate limit
            current_count = len(self.rate_limit_tracker[user_id])
            limit_per_minute = max(1, self.rate_limit // 60)  # Prevent division issues
            
            if current_count >= limit_per_minute:
                audit_logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "user_id": user_id,
                        "count": current_count,
                        "limit": limit_per_minute,
                        "agent": self.id
                    }
                )
                return False, f"Rate limit exceeded. Max {limit_per_minute} queries/minute"
            
            # Add current timestamp
            self.rate_limit_tracker[user_id].append(now)
        
        return True, "Rate limit OK"

    async def process_query(self, query: str, database_connection: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:

        if not query or not isinstance(query, str):
            return {
                "success": False,
                "error": "Query must be a non-empty string",
                "response": "Invalid input provided.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }
        
        if len(query) > 10000:  # 10KB limit
            return {
                "success": False,
                "error": f"Query too long: {len(query)} bytes (max 10000)",
                "response": "Your question is too long. Please ask a shorter question.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }
        
        try:
            from ..tools import database_introspection_tool, sql_execution_tool
        except (ImportError, ModuleNotFoundError) as e:
            audit_logger.error(
                "Failed to import tools",
                extra={"error_type": type(e).__name__, "user_id": user_id, "agent": self.id}
            )
            return {
                "success": False,
                "error": "Service unavailable",
                "response": "Service configuration error. Please try again later.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }
        
        # LOOPHOLE FIX 8: Check rate limit first
        is_allowed, rate_msg = self.check_rate_limit(user_id)
        if not is_allowed:
            return {
                "success": False,
                "error": rate_msg,
                "response": "Too many requests. Please try again in a moment.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }
        
        # Log audit trail (LOOPHOLE FIX 9: Never log database URL)
        audit_logger.info(
            "Query received",
            extra={
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "query_length": len(query),
                "agent": self.id,
                "database": "***"  # Never expose actual URL
            }
        )

        if not database_connection:
            database_connection = self.database_url

        if not database_connection:
            error_response = {
                "success": False,
                "error": "Database not configured",
                "response": "System configuration error. Please contact support.",
                "timestamp": datetime.now().isoformat()
            }
            audit_logger.error("Database not configured", extra={"user_id": user_id, "agent": self.id})
            return error_response

        try:
            # Step 1: Get schema (cached for 1 hour)
            schema = await database_introspection_tool(database_connection)
            
            if schema is None:
                raise ValueError("Schema introspection returned None")
            
            if not hasattr(schema, 'tables') or not hasattr(schema, 'database'):
                raise AttributeError("Schema object missing required attributes (tables, database)")
            
            tables_list = getattr(schema, 'tables', [])
            if not isinstance(tables_list, list):
                raise TypeError(f"Schema.tables should be list, got {type(tables_list)}")
            
            # Log successful schema retrieval (no URL)
            audit_logger.info(
                "Schema retrieved",
                extra={
                    "user_id": user_id,
                    "tables": len(tables_list),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Step 2: Return analysis with schema information
            tables_available = []
            for t in tables_list:
                if hasattr(t, 'table_name'):
                    tables_available.append(t.table_name)
            
            return {
                "success": True,
                "query": query,
                "database": getattr(schema, 'database', 'neondb'),
                "tables_available": tables_available,
                "table_count": len(tables_list),
                "response": f"I've analyzed the {getattr(schema, 'database', 'neondb')} database with {len(tables_list)} tables. Please ask your question about colleges, cutoffs, programs, or admissions.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "agent": self.id
            }
        except (ValueError, AttributeError, TypeError) as e:
            audit_logger.error(
                "Query processing failed",
                extra={
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                    "query": query[:100],
                    "timestamp": datetime.now().isoformat()
                }
            )
            return {
                "success": False,
                "error": "Query processing failed",
                "response": "I encountered a temporary issue. Please try again in a moment.",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            }


# Production Singleton Instance (Security-Initialized)
college_agent = CollegeAgent()

# Log agent initialization
audit_logger.info(
    "College Counselling Agent initialized",
    extra={
        "model": college_agent.model,
        "temperature": college_agent.temperature,
        "max_tokens": college_agent.max_tokens,
        "timeout": college_agent.timeout,
        "db_provider": college_agent.db_provider,
        "timestamp": datetime.now().isoformat()
    }
)
