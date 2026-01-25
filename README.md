# TNEA College Counselling Assistant

A professional, AI-powered college counselling assistant built with Mastra. This agent helps prospective students, parents, and advisors answer questions about colleges, programs, admissions cutoffs, fees, eligibility, and application strategies by querying a PostgreSQL database containing college and admissions data.

## Features

- **Natural Language Queries**: Ask questions in plain English about colleges, cutoffs, fees, programs, and admissions
- **Database-Driven Answers**: Retrieves factual, accurate data from a PostgreSQL database
- **Professional Guidance**: Provides recommendations, explains admission criteria, and offers application strategies
- **Safe & Secure**: Only executes read-only SELECT queries
- **Conversational Memory**: Remembers context across questions for personalized assistance

## Project Structure

```
src/
├── mastra/
│   ├── agents/
│   │   └── sql-agent.ts                    # SQL agent for query generation
│   ├── tools/
│   │   ├── database-introspection-tool.ts  # Database schema analysis
│   │   ├── database-seeding-tool.ts        # Database seeding
│   │   ├── sql-generation-tool.ts          # Natural language to SQL conversion
│   │   └── sql-execution-tool.ts           # Safe SQL query execution
│   ├── workflows/
│   │   └── database-query-workflow.ts      # Main workflow orchestration
│   └── index.ts                           # Mastra instance configuration

```

## Tools Overview

### 1. Database Introspection Tool (`database-introspection-tool.ts`)

Analyzes a PostgreSQL database to extract:

- Table structure and metadata
- Column definitions with types and constraints
- Primary key and foreign key relationships
- Index definitions
- Row counts for each table

**Input**: Database connection string
**Output**: Complete schema information with summary statistics

### 2. Database Seeding Tool (`database-seeding-tool.ts`)

Seeds databases with sample data for testing:

- Creates cities table with proper schema
- Imports data from CSV or generates sample data
- Handles batch insertions efficiently
- Returns seeding statistics and metadata

**Input**: Database connection string
**Output**: Seeding results with record counts and success status

### 3. SQL Generation Tool (`sql-generation-tool.ts`)

Converts natural language queries to SQL using OpenAI's GPT-4:

- Analyzes database schema context
- Generates optimized SELECT queries
- Provides confidence scores and explanations
- Lists assumptions and tables used

**Input**: Natural language query + database schema
**Output**: SQL query with metadata and explanations

### 4. SQL Execution Tool (`sql-execution-tool.ts`)

Safely executes SQL queries:

- Restricts to SELECT queries only
- Manages connection pooling
- Provides detailed error handling
- Returns structured results

**Input**: Connection string + SQL query
**Output**: Query results or error information

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies
npm install

# Configure .env file
cp .env.example .env
# Edit .env and add:
# - DATABASE_URL: Your PostgreSQL connection string
# - GROQ_API_KEY (or other AI provider key based on MODEL setting)
```

### 2. Expected Database Schema

The agent works best with a college/admissions MySQL database containing tables like:

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

## Dependencies

Key dependencies:

- `@mastra/core`: Workflow orchestration
- `ai`: AI SDK for structured generation
- `pg`: PostgreSQL client
- `zod`: Schema validation
