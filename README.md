# TNEA College Counselling Assistant

A robust, AI-powered college counselling system that helps prospective students find the right college matches through natural language processing and intelligent database queries.

## 🎯 Overview

The TNEA College Counselling Assistant is a production-grade application that processes student queries through a multi-stage workflow:

```
User Question
     ↓
[NLP Processing]
     ↓
[Schema Understanding]
     ↓
[SQL Generation]
     ↓
[Query Execution]
     ↓
[Result Formatting]
     ↓
Structured Response
```

## 📊 System Architecture

### Core Components

```
src/
├── tools/                                    # Data processing tools
│   ├── database_introspection_tool.py       # Schema analysis & caching
│   ├── sql_generation_tool.py               # NLP to SQL conversion
│   └── sql_execution_tool.py                # Safe query execution
│
├── agents/                                   # AI agents
│   ├── college_agent.py                     # Main counselling agent
│   └── sql_generation_agent.py              # SQL generation specialist
│
├── workflows/                                # Business logic
│   └── database_query_workflow.py           # Query orchestration
│
└── api.py                                   # Service layer
```

## 🔄 Workflow Stages

### 1. Schema Introspection
- **Purpose**: Understand the complete database structure
- **Process**: Connects to PostgreSQL and extracts table/column metadata
- **Output**: Cached schema information (1-hour TTL)
- **Tools Used**: `database_introspection_tool`

**Database Tables:**
```
- colleges (461 records)
  └─ college_code, college_name, location, region, college_type

- branch (113 records)
  └─ id, branch_code, branch_name, category

- candidate_allotment (511K+ records)
  └─ id, s_no, aggr_mark, general_rank, community, college_code, branch_code, year, round
```

### 2. Natural Language Processing
- **Purpose**: Extract intent from user questions
- **Input**: Raw user question (e.g., "colleges in Chennai")
- **Process**: Analyze question patterns and keywords
- **Output**: Structured query intent
- **Handled By**: `college_agent`

### 3. SQL Generation
- **Purpose**: Convert natural language to database queries
- **Strategy**: Dual-approach system
  - **Primary**: Groq LLM for intelligent queries
  - **Fallback**: Rule-based patterns for reliability
- **Examples**:
  - "colleges in location" → `SELECT * FROM colleges WHERE location LIKE ?`
  - "list branches" → `SELECT * FROM branch`
  - "allotments" → `SELECT * FROM candidate_allotment`
- **Tools Used**: `sql_generation_tool`

### 4. Query Execution
- **Purpose**: Execute queries safely against postgreSQL
- **Constraints**:
  - SELECT-only (no INSERT/UPDATE/DELETE)
  - Pattern validation
  - SQL injection prevention
  - Result limiting
- **Output**: Structured JSON with results
- **Tools Used**: `sql_execution_tool`

### 5. Response Formatting
- **Purpose**: Present results to user
- **Format**: JSON with metadata
- **Includes**:
  - Generated SQL (for transparency)
  - Result set
  - Row count
  - Execution timestamp
  - Error messages (if any)

## 🤖 Agent Architecture

### College Counselling Agent
**Role**: Primary interaction point with students and advisors

**Capabilities**:
- Understand college-related questions
- Provide contextual recommendations
- Explain admission criteria
- Compare colleges based on location, type, programs
- Handle follow-up questions with context

**System Prompt**:
```
You are a professional, empathetic college counselling assistant.
- Answer factual questions using the database
- Provide recommendations with explanations
- Explain trade-offs (cost vs ranking vs placement)
- Use professional but accessible language
```

### SQL Generation Agent
**Role**: Convert natural language to database queries

**Capabilities**:
- Analyze database schema
- Generate efficient SELECT queries
- Validate query safety
- Provide fallback patterns
- Optimize for result size

**System Prompt**:
```
You are an expert SQL query generator for college databases.
- Convert questions to precise SELECT queries
- Use appropriate JOINs and WHERE clauses
- Always include LIMIT to prevent huge datasets
- Think about what data would actually answer the question
```

## 🔐 Security & Reliability

### Query Safety
✓ SELECT-only enforcement  
✓ Parameterized query support  
✓ Pattern-based validation  
✓ Dangerous keyword blocking  
✓ Connection pooling  
✓ Timeout management  

### Data Validation
✓ Pydantic request validation  
✓ Schema cache verification  
✓ Result type checking  
✓ Error handling & logging  

### Error Recovery
✓ LLM failure graceful fallback  
✓ Connection retry logic  
✓ Query timeout handling  
✓ Detailed error messages  

## 📝 Processing Pipeline

### User Query Flow

```python
# 1. Question Arrival
question = "Which colleges have AI programs in Chennai?"

# 2. Schema Loading
schema = cache.get_or_fetch()  # Cached for 1 hour

# 3. Intent Recognition
intent = analyze_question(question)
# Result: {"type": "colleges", "filter": "location", "value": "Chennai"}

# 4. SQL Generation
sql = generate_sql(question, schema)
# Result: "SELECT * FROM colleges WHERE location ILIKE 'Chennai' LIMIT 20"

# 5. Query Execution
results = execute_query(sql, connection)
# Result: List of college records

# 6. Response Building
response = {
    "success": True,
    "question": question,
    "generated_sql": sql,
    "results": results,
    "row_count": len(results),
    "timestamp": "2026-03-10T11:00:00"
}
```

## 🛠️ Key Dependencies

**Backend Framework**:
- FastAPI 0.115+
- Uvicorn (ASGI server)
- Pydantic 2.0+ (validation)

**Database**:
- PostgreSQL (via psycopg2)
- SQLAlchemy (optional ORM)

**AI/LLM**:
- Groq (primary LLM provider)
- OpenAI (fallback)

**Environment**:
- Python 3.10+
- asyncio for concurrency
- python-dotenv for config

## 🚀 Deployment Considerations

### Production Setup
1. **Database Connection**: PostgreSQL on Neon (or similar)
2. **Environment Variables**: DATABASE_URL, GROQ_API_KEY
3. **Server**: Uvicorn with worker processes
4. **Monitoring**: Error logging and query analytics
5. **Caching**: Redis for distributed caching (optional)

### Scaling Strategy
- Async query processing for concurrent requests
- Schema cache with TTL
- Connection pooling
- Result pagination for large datasets

## 📋 Configuration

Create `.env` file:
```bash
# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/database

# LLM
GROQ_API_KEY=your_groq_key

# Server
PORT=8000
HOST=0.0.0.0
DEBUG=false
```

## 🧪 Testing

**Comprehensive Test Suite**:
```bash
python3 final_test.py
```

Tests verify:
- Database connectivity
- Schema retrieval
- NLP to SQL conversion
- Direct SQL execution
- Error handling
- Response formatting

## 💡 Example Use Cases

**Student Queries**:
- "What engineering colleges are in Chennai?"
- "Show me colleges with lower competition"
- "Which branches offer AI programs?"
- "Colleges in urban areas with good placement"

**Administrative Queries**:
- "Total allotments this round?"
- "College-wise seat availability"
- "Most competitive branches"
- "Regional distribution analysis"

## 📊 Database Statistics

| Table | Records | Purpose |
|-------|---------|---------|
| colleges | 461 | College information & metadata |
| branch | 113 | Engineering branch catalog |
| candidate_allotment | 511K+ | Historical allotment data |

### Key Queries Supported

```sql
-- College search
SELECT * FROM colleges WHERE location ILIKE 'Chennai'

-- Branch information
SELECT DISTINCT category FROM branch

-- Allotment statistics
SELECT COUNT(*) as total_allotments FROM candidate_allotment

-- College by region
SELECT DISTINCT region FROM colleges
```

## ✨ Feature Highlights

✓ **Intelligent NLP Processing**: Understands various phrasings of same question  
✓ **Dual-Strategy SQL Generation**: LLM + rule-based fallback  
✓ **Schema Caching**: 1-hour TTL for performance  
✓ **Error Recovery**: Graceful degradation on failures  
✓ **Production Ready**: Logging, validation, security  
✓ **Async Processing**: Handles concurrent requests  

## 🔧 Troubleshooting

**Issue**: LLM not responding  
**Resolution**: System falls back to rule-based SQL generation  

**Issue**: Schema cache outdated  
**Resolution**: Auto-refresh after 1 hour or manual refresh available  

**Issue**: Query timeout  
**Resolution**: Automatic result limiting prevents huge datasets  

**Issue**: Connection failures  
**Resolution**: Retry logic with exponential backoff  

## 📚 Architecture Principles

1. **Separation of Concerns**: Tools, agents, workflows isolated
2. **Fault Tolerance**: Multiple fallback strategies
3. **Performance**: Caching, async, connection pooling
4. **Security**: Read-only, validated inputs, error sanitization
5. **Maintainability**: Clear documentation, consistent patterns
6. **Scalability**: Stateless design for horizontal scaling

## 🎯 Next Steps

1. Deploy PostgreSQL database with college data
2. Configure environment variables
3. Start service: `python3 api.py`
4. Test workflows: `python3 final_test.py`
5. Monitor query patterns and performance
6. Add custom business logic as needed

---

**Version**: 1.0.0  
**Last Updated**: March 2026  
**Status**: Production Ready  
**Database**: PostgreSQL (Neon)  
**Language**: Python 3.10+

```sql
-- Colleges table
CREATE TABLE colleges (
  id INT PRIMARY KEY AUTO_INCREMENT,
  college_name VARCHAR(255) NOT NULL,
  location VARCHAR(255),
  state VARCHAR(100),
  city VARCHAR(100),
  type VARCHAR(50), -- Government/Private/Autonomous
  affiliation VARCHAR(100),
  ranking INT,
  placement_rate DECIMAL(5,2)
);

-- Programs table
CREATE TABLE programs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  college_id INT,
  program_name VARCHAR(255) NOT NULL,
  program_code VARCHAR(50),
  degree_type VARCHAR(50), -- BE/BTech/ME/MTech/etc
  duration_years INT,
  total_seats INT,
  FOREIGN KEY (college_id) REFERENCES colleges(id)
);

-- Cutoffs table
CREATE TABLE cutoffs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  program_id INT,
  admission_year INT NOT NULL,
  category VARCHAR(50), -- General/OBC/SC/ST/etc
  cutoff_rank INT,
  cutoff_percentage DECIMAL(5,2),
  opening_rank INT,
  closing_rank INT,
  FOREIGN KEY (program_id) REFERENCES programs(id)
);

-- Fees table
CREATE TABLE fees (
  id INT PRIMARY KEY AUTO_INCREMENT,
  program_id INT,
  academic_year VARCHAR(20),
  tuition_fee DECIMAL(10,2),
  hostel_fee DECIMAL(10,2),
  total_fee DECIMAL(10,2),
  FOREIGN KEY (program_id) REFERENCES programs(id)
);
```

### 3. Using the College Agent

```typescript
import { mastra } from './src/mastra';

const collegeAgent = mastra.getAgent('collegeAgent');

// Example: Ask about cutoffs
const result = await collegeAgent.generate(
  [
    {
      role: 'user',
      content: 'Which colleges have Computer Science programs with cutoff below 5000 rank for General category in 2024?',
    },
  ],
  { 
    maxSteps: 10,
    resourceid: process.env.DATABASE_URL // Pass DB connection
  },
);

console.log(result.text);
```

### 4. Example Questions

**Cutoff Queries:**
- "What was the closing rank for CSE at Anna University in 2024 for OBC category?"
- "Show me all engineering colleges with General category cutoff below 10000"

**Fee Queries:**
- "What are the fees for BTech programs in Chennai under 100K per year?"
- "Compare tuition fees between government and private colleges for ECE"

**Program Recommendations:**
- "I scored 85% in 12th grade. Which colleges can I get for Mechanical Engineering?"
- "Suggest affordable colleges in Tamil Nadu for Computer Science with good placement"

**Location-Based:**
- "List all autonomous engineering colleges in Coimbatore"
- "Which colleges in Chennai offer Artificial Intelligence programs?"

### Agent Capabilities

✅ **Database-Driven Answers** - Queries actual college data for accurate responses  
✅ **Smart Recommendations** - Suggests colleges based on scores, budget, location  
✅ **Multi-Criteria Filtering** - Combines cutoff, fees, location, ranking in queries  
✅ **Safe & Accurate** - Only executes SELECT queries; explains all assumptions  
✅ **Conversational** - Remembers context and provides personalized guidance

## Workflows

### Database Query Workflow (Multi-Step with Suspend/Resume)

The main workflow (`databaseQueryWorkflow`) is a multi-step interactive workflow that performs:

#### Step 1: Database Connection

- **Suspends** to collect database connection string from user
- **Validates** connection to ensure database is accessible

#### Step 2: Database Seeding (Optional)

- **Suspends** to ask if user wants to seed database with sample data
- **Creates** cities table with sample data if requested
- **Provides** immediate data for testing and demonstration

#### Step 3: Schema Introspection

- **Automatically** introspects database schema (tables, columns, relationships, indexes)
- **Generates** human-readable schema presentation
- **Analyzes** database structure and relationships

#### Step 4: Natural Language to SQL Generation

- **Suspends** to collect natural language query from user
- **Shows** database schema information to help user formulate queries
- **Generates** SQL query using AI with confidence scores and explanations

#### Step 5: SQL Review and Execution

- **Suspends** to show generated SQL and get user approval
- **Allows** user to modify the SQL query if needed
- **Executes** the approved/modified query against the database
- **Returns** query results with metadata

**Usage**:

```typescript
const workflow = mastra.getWorkflow('databaseQueryWorkflow');
const run = await workflow.createRun();

// Start workflow (will suspend for connection string)
let result = await run.start({ inputData: {} });

// Step 1: Provide connection string
result = await run.resume({
  step: 'get-connection',
  resumeData: { connectionString: 'postgresql://...' },
});

// Step 2: Choose whether to seed database
result = await run.resume({
  step: 'seed-database',
  resumeData: { seedDatabase: true },
});

// Step 3: Database introspection happens automatically

// Step 4: Provide natural language query
result = await run.resume({
  step: 'generate-sql',
  resumeData: { naturalLanguageQuery: 'Show me top 10 cities by population' },
});

// Step 5: Review and approve SQL
result = await run.resume({
  step: 'review-and-execute',
  resumeData: {
    approved: true,
    modifiedSQL: 'optional modified query',
  },
});
```

## Setup and Installation

1. **Install Dependencies**:

```bash
pnpm install
```

2. **Environment Setup**:
   Create a `.env` file with your database connection:

```env
OPENAI_API_KEY=your-openai-api-key
```

## Model Configuration

This template supports any AI model provider through Mastra's model router. You can use models from:

- **OpenAI**: `openai/gpt-4o-mini`, `openai/gpt-4o`
- **Anthropic**: `anthropic/claude-sonnet-4-5-20250929`, `anthropic/claude-haiku-4-5-20250929`
- **Google**: `google/gemini-2.5-pro`, `google/gemini-2.0-flash-exp`
- **Groq**: `groq/llama-3.3-70b-versatile`, `groq/llama-3.1-8b-instant`
- **Cerebras**: `cerebras/llama-3.3-70b`
- **Mistral**: `mistral/mistral-medium-2508`

Set the `MODEL` environment variable in your `.env` file to your preferred model.

## Security Notes

- Only SELECT queries are allowed for security
- Connection strings should be securely managed
- The system uses connection pooling for efficiency
- All database operations are logged for audit trails

## Current Features

✅ **Database Schema Introspection** - Automatically analyzes database structure
✅ **Database Seeding** - Optional sample data creation for testing and demos
✅ **Human-readable Documentation** - Generates beautiful schema presentations
✅ **Natural Language to SQL** - AI-powered query generation with explanations
✅ **Interactive Workflows** - Multi-step suspend/resume for human-in-the-loop
✅ **Conversational Agent** - Enhanced SQL agent with full workflow capabilities
✅ **SQL Review & Editing** - User can approve or modify generated queries
✅ **Safe Query Execution** - Only allows SELECT queries with result display
✅ **Multi-tool Orchestration** - Agent automatically uses appropriate tools
✅ **Type Safety** - Full TypeScript support with Zod validation
✅ **Error Handling** - Comprehensive error management throughout workflow

## Enhanced Dataset

The seeding tool now provides a comprehensive business dataset with realistic relationships:

### **📊 Dataset Overview**

- **5 Companies** across different industries (Technology, Finance, Healthcare, etc.)
- **7 Office Locations** with geographic distribution
- **14 Departments** with budgets and head counts
- **20 Job Titles** with career levels (Junior, Mid, Senior, Staff, Management)
- **20 Skills** across programming languages, frameworks, and tools
- **~100-150 Employees** with realistic salary distributions
- **~40-60 Projects** with various statuses and budgets
- **Relationships**: Employee-skill mappings, project assignments, salary history

### **💡 Query Ideas**

The enhanced dataset supports queries about:

- Employee hierarchies and reporting structures
- Skill distributions and proficiency levels
- Project team compositions and allocations
- Salary analysis and career progression
- Cross-company comparisons and analytics
- Geographic workforce distribution
- Department budgets and performance
- Employee-skill matching for projects
- Compensation history and trends
- Multi-table joins with complex relationships
