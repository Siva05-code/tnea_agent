import { createWorkflow, createStep } from '@mastra/core/workflows';
import { z } from 'zod';
import { databaseIntrospectionTool } from '../tools/database-introspection-tool';
import { sqlGenerationTool } from '../tools/sql-generation-tool';
import { sqlExecutionTool } from '../tools/sql-execution-tool';

// Step 1: Introspect database to get schema
const introspectDatabaseStep = createStep({
  id: 'introspect-database',
  inputSchema: z.object({}),
  outputSchema: z.object({
    schema: z.any(),
    schemaPresentation: z.string(),
  }),
  execute: async () => {
    const connectionString = process.env.DATABASE_URL;

    if (!connectionString) {
      throw new Error('DATABASE_URL environment variable not set');
    }

    try {
      console.log('🔍 Introspecting database...');

      if (!databaseIntrospectionTool.execute) {
        throw new Error('Database introspection tool is not available');
      }

      const schemaData = await databaseIntrospectionTool.execute(
        {
          connectionString,
        },
        {} as any,
      );

      const schemaPresentation = createSchemaPresentation(schemaData);

      return {
        schema: schemaData,
        schemaPresentation,
      };
    } catch (error) {
      throw new Error(`Failed to introspect database: ${error instanceof Error ? error.message : String(error)}`);
    }
  },
});

// Step 2: Get natural language query
const getQueryStep = createStep({
  id: 'get-query',
  inputSchema: z.object({
    schema: z.any(),
    schemaPresentation: z.string(),
  }),
  outputSchema: z.object({
    query: z.string(),
    schemaPresentation: z.string(),
  }),
  resumeSchema: z.object({
    query: z.string(),
  }),
  suspendSchema: z.object({
    schema: z.string(),
    message: z.string(),
  }),
  execute: async ({ inputData, resumeData, suspend }) => {
    const { schemaPresentation } = inputData;

    if (!resumeData?.query) {
      await suspend({
        schema: schemaPresentation,
        message: 'Enter your natural language question about the college data:',
      });

      return {
        query: '',
        schemaPresentation,
      };
    }

    return {
      query: resumeData.query,
      schemaPresentation,
    };
  },
});

// Step 3: Generate SQL
const generateSQLStep = createStep({
  id: 'generate-sql',
  inputSchema: z.object({
    query: z.string(),
    schemaPresentation: z.string(),
  }),
  outputSchema: z.object({
    query: z.string(),
    sqlInfo: z.any(),
  }),
  execute: async ({ inputData }) => {
    const { query } = inputData;

    try {
      console.log(`\n📝 Generating SQL for: "${query}"\n`);

      if (!sqlGenerationTool.execute) {
        throw new Error('SQL generation tool is not available');
      }

      const sqlInfo = await sqlGenerationTool.execute(
        {
          question: query,
        },
        {} as any,
      );

      return {
        query,
        sqlInfo,
      };
    } catch (error) {
      throw new Error(`Failed to generate SQL: ${error instanceof Error ? error.message : String(error)}`);
    }
  },
});

// Step 4: Get SQL to execute from user
const getSQLToExecuteStep = createStep({
  id: 'get-sql-to-execute',
  inputSchema: z.object({
    query: z.string(),
    sqlInfo: z.any(),
  }),
  outputSchema: z.object({
    query: z.string(),
    sql: z.string(),
  }),
  resumeSchema: z.object({
    sql: z.string(),
  }),
  suspendSchema: z.object({
    message: z.string(),
    sqlInfo: z.string(),
  }),
  execute: async ({ inputData, resumeData, suspend }) => {
    if (!resumeData?.sql) {
      await suspend({
        message: 'Please provide the SQL query to execute (or press Enter to skip):',
        sqlInfo: JSON.stringify(inputData.sqlInfo, null, 2),
      });

      return {
        query: inputData.query,
        sql: '',
      };
    }

    return {
      query: inputData.query,
      sql: resumeData.sql,
    };
  },
});

// Step 5: Execute SQL
const executeSQLStep = createStep({
  id: 'execute-sql',
  inputSchema: z.object({
    sql: z.string(),
    query: z.string(),
  }),
  outputSchema: z.object({
    query: z.string(),
    sql: z.string(),
    results: z.any(),
    rowCount: z.number(),
  }),
  execute: async ({ inputData }) => {
    const { sql, query } = inputData;

    if (!sql.trim()) {
      return {
        query,
        sql,
        results: [],
        rowCount: 0,
      };
    }

    try {
      console.log(`\n🚀 Executing SQL...\n`);

      if (!sqlExecutionTool.execute) {
        throw new Error('SQL execution tool is not available');
      }

      const connectionString = process.env.DATABASE_URL;
      if (!connectionString) {
        throw new Error('DATABASE_URL not set');
      }

      const result = await sqlExecutionTool.execute(
        {
          query: sql,
          connectionString,
        },
        {} as any,
      );

      const resultData = result as any;

      if (resultData && !resultData.success && resultData.error) {
        throw new Error(String(resultData.error));
      }

      return {
        query,
        sql,
        results: resultData?.data || [],
        rowCount: resultData?.rowCount || 0,
      };
    } catch (error) {
      throw new Error(`Failed to execute SQL: ${error instanceof Error ? error.message : String(error)}`);
    }
  },
});

// Create the workflow
export const databaseQueryWorkflow = createWorkflow({
  id: 'database-query-workflow',
  inputSchema: z.object({}),
  outputSchema: z.object({
    query: z.string(),
    sql: z.string(),
    results: z.any(),
    rowCount: z.number(),
  }),
  steps: [introspectDatabaseStep, getQueryStep, generateSQLStep, getSQLToExecuteStep, executeSQLStep],
});

databaseQueryWorkflow
  .then(introspectDatabaseStep)
  .then(getQueryStep)
  .then(generateSQLStep)
  .then(getSQLToExecuteStep)
  .then(executeSQLStep)
  .commit();

// Helper function to create human-readable schema presentation
function createSchemaPresentation(schema: any): string {
  let presentation = '# Database Schema Overview\n\n';

  presentation += `## Summary\n`;
  presentation += `- **Tables**: ${schema.summary.total_tables}\n`;
  presentation += `- **Columns**: ${schema.summary.total_columns}\n`;
  presentation += `- **Relationships**: ${schema.summary.total_relationships}\n`;
  presentation += `- **Indexes**: ${schema.summary.total_indexes}\n\n`;

  // Group columns by table
  const tableColumns = new Map<string, any[]>();
  schema.columns.forEach((column: any) => {
    const tableKey = `${column.table_schema}.${column.table_name}`;
    if (!tableColumns.has(tableKey)) {
      tableColumns.set(tableKey, []);
    }
    tableColumns.get(tableKey)?.push(column);
  });

  presentation += `## Tables and Columns\n\n`;

  schema.tables.forEach((table: any) => {
    const tableKey = `${table.schema_name}.${table.table_name}`;
    const columns = tableColumns.get(tableKey) || [];
    const rowCount = schema.rowCounts.find(
      (rc: any) => rc.schema_name === table.schema_name && rc.table_name === table.table_name,
    );

    presentation += `### ${table.table_name}`;
    if (rowCount) {
      presentation += ` (${rowCount.row_count.toLocaleString()} rows)`;
    }
    presentation += `\n\n`;

    presentation += `| Column | Type | Nullable | Key | Default |\n`;
    presentation += `|--------|------|----------|-----|----------|\n`;

    columns.forEach((column: any) => {
      const type = column.character_maximum_length
        ? `${column.data_type}(${column.character_maximum_length})`
        : column.data_type;
      const nullable = column.is_nullable === 'YES' ? '✓' : '✗';
      const key = column.is_primary_key ? 'PK' : '';
      const defaultValue = column.column_default || '';

      presentation += `| ${column.column_name} | ${type} | ${nullable} | ${key} | ${defaultValue} |\n`;
    });

    presentation += `\n`;
  });

  if (schema.relationships && schema.relationships.length > 0) {
    presentation += `## Relationships\n\n`;
    schema.relationships.forEach((rel: any) => {
      presentation += `- **${rel.table_name}.${rel.column_name}** → **${rel.foreign_table_name}.${rel.foreign_column_name}**\n`;
    });
    presentation += `\n`;
  }

  if (schema.indexes && schema.indexes.length > 0) {
    presentation += `## Indexes\n\n`;
    schema.indexes.forEach((index: any) => {
      presentation += `- **${index.table_name}**: ${index.index_name}\n`;
    });
    presentation += `\n`;
  }

  presentation += `---\n`;
  presentation += `Database schema introspection complete!`;

  return presentation;
}
