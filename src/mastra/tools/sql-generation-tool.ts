import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import mysql from 'mysql2/promise';

export const sqlGenerationTool = createTool({
  id: 'sql-generation',
  inputSchema: z.object({
    question: z.string().describe('Natural language question about colleges and admissions'),
    generateOnly: z
      .boolean()
      .optional()
      .describe('If true, only generate SQL without executing. If false, generate and execute.'),
  }),
  description:
    'Generates SQL SELECT queries from natural language questions. First introspects database schema, then generates appropriate SQL.',
  execute: async inputData => {
    const { question, generateOnly = false } = inputData;
    const dbUrl = process.env.DATABASE_URL;

    if (!dbUrl) {
      throw new Error('DATABASE_URL environment variable not set');
    }

    let connection: mysql.Connection | null = null;

    try {
      console.log(`📝 Processing question: "${question}"\n`);

      connection = await mysql.createConnection({
        uri: dbUrl,
        connectTimeout: 30000,
      });

      // Get database name
      const [dbResult] = await connection.execute('SELECT DATABASE() as db_name');
      const currentDb = (dbResult as any[])[0]?.db_name;
      console.log(`📊 Database: ${currentDb}\n`);

      // Get table information
      const [tables] = await connection.execute(
        `SELECT TABLE_NAME FROM information_schema.TABLES 
         WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME`,
        [currentDb],
      );

      const tableNames = (tables as any[]).map(t => t.TABLE_NAME);
      console.log(`📋 Available tables: ${tableNames.join(', ')}\n`);

      // Get columns information
      const [columns] = await connection.execute(
        `SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY, IS_NULLABLE
         FROM information_schema.COLUMNS 
         WHERE TABLE_SCHEMA = ? 
         ORDER BY TABLE_NAME, ORDINAL_POSITION`,
        [currentDb],
      );

      // Build schema context
      const schemaContext = buildSchemaText(columns as any[]);

      return {
        success: true,
        question,
        database: currentDb,
        tables: tableNames,
        schemaContext,
        nextInstruction:
          'Now use sql-execution tool to execute the query. The LLM should generate a SELECT query based on the schema context.',
      };
    } catch (error) {
      throw new Error(`Failed to generate SQL: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      if (connection) {
        await connection.end();
      }
    }
  },
});

function buildSchemaText(columns: any[]): string {
  const tableColumns = new Map<string, any[]>();

  columns.forEach((col: any) => {
    if (!tableColumns.has(col.TABLE_NAME)) {
      tableColumns.set(col.TABLE_NAME, []);
    }
    tableColumns.get(col.TABLE_NAME)?.push(col);
  });

  let text = 'DATABASE SCHEMA:\n\n';

  for (const [tableName, cols] of tableColumns) {
    text += `TABLE: ${tableName}\n`;
    cols.forEach((col: any) => {
      const pk = col.COLUMN_KEY === 'PRI' ? ' [PRIMARY KEY]' : '';
      const nullable = col.IS_NULLABLE === 'YES' ? '' : ' [NOT NULL]';
      text += `  - ${col.COLUMN_NAME}: ${col.DATA_TYPE}${pk}${nullable}\n`;
    });
    text += '\n';
  }

  return text;
}
