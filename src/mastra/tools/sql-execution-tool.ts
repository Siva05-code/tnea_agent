import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import mysql from 'mysql2/promise';

const createDatabaseConnection = async (connectionString: string) => {
  return await mysql.createConnection({
    uri: connectionString,
    connectTimeout: 30000, // 30 seconds
  });
};

const executeQuery = async (connection: mysql.Connection, query: string) => {
  try {
    console.log('Executing query:', query);
    const [rows] = await connection.execute(query);
    console.log('Query result:', rows);
    return rows as any[];
  } catch (error) {
    throw new Error(`Failed to execute query: ${error instanceof Error ? error.message : String(error)}`);
  }
};

const ALLOWED_FUNCTIONS = new Set([
  'count',
  'sum',
  'avg',
  'min',
  'max',
  'upper',
  'lower',
  'length',
  'substring',
  'date_part',
  'now',
  'current_timestamp',
  'current_date',
  'coalesce',
  'greatest',
  'least',
]);

/**
 * Sanitize SQL query by removing string literals and comments before pattern matching.
 * This prevents false positives from dangerous patterns appearing in string literals.
 */
const sanitizeQueryForPatternMatching = (query: string): string => {
  let sanitized = query;

  // Remove single-quoted string literals (handle escaped quotes)
  sanitized = sanitized.replace(/'(?:''|[^'])*'/g, "''");

  // Remove double-quoted identifiers (handle escaped quotes)
  sanitized = sanitized.replace(/"(?:""|[^"])*"/g, '""');

  // Remove multi-line /* */ comments
  sanitized = sanitized.replace(/\/\*[\s\S]*?\*\//g, ' ');

  // Remove single-line -- comments
  sanitized = sanitized.replace(/--.*$/gm, ' ');

  // Normalize whitespace
  sanitized = sanitized.replace(/\s+/g, ' ');

  return sanitized.toLowerCase();
};

const validateQuery = (query: string) => {
  const trimmedQuery = query.trim().toLowerCase();

  if (!trimmedQuery.startsWith('select')) {
    throw new Error('Only SELECT queries are allowed for security reasons');
  }

  // Sanitize the query by removing string literals and comments before checking patterns
  const normalizedQuery = sanitizeQueryForPatternMatching(query);

  // Block common dangerous patterns with more robust regex
  const dangerousPatterns = [
    // MySQL system functions and commands
    /\bmysql\s*\(/i,
    /\bload_file\s*\(/i,
    /\binto\s+outfile/i,
    /\binto\s+dumpfile/i,

    // Information schema access (allowed but monitored)
    // /information_schema/i,

    // File operations
    /\bcopy\s+/i,
    /\bload\s+data/i,

    // Code evaluation and execution
    /\beval\s*\(/i,
    /\bexecute\s+/i,
    /\bprepare\s+/i,

    // Time/resource manipulation
    /\bsleep\s*\(/i,
    /\bbenchmark\s*\(/i,

    // Administrative functions
    /\buser\s*\(/i,
    /\bdatabase\s*\(/i,
    /\bversion\s*\(/i,

    // Network functions
    /\bconnection_id\s*\(/i,
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(normalizedQuery)) {
      throw new Error(`Query contains potentially dangerous operations: matched pattern ${pattern}`);
    }
  }

  // Extract and validate function calls more robustly
  const functionPattern = /\b(?:\w+\.)?(\w+)\s*\(/g;
  let match;
  while ((match = functionPattern.exec(normalizedQuery)) !== null) {
    const functionName = match[1].trim().toLowerCase();
    if (!ALLOWED_FUNCTIONS.has(functionName)) {
      throw new Error(`Function '${functionName}' is not allowed for security reasons`);
    }
  }

  // Additional checks for SQL injection patterns
  const injectionPatterns = [
    /;\s*drop\s+/i,
    /;\s*delete\s+/i,
    /;\s*update\s+/i,
    /;\s*insert\s+/i,
    /;\s*create\s+/i,
    /;\s*alter\s+/i,
    /union\s+.*select/i,
  ];

  for (const pattern of injectionPatterns) {
    if (pattern.test(normalizedQuery)) {
      throw new Error('Query contains potentially malicious SQL injection patterns');
    }
  }
};

export const sqlExecutionTool = createTool({
  id: 'sql-execution',
  inputSchema: z.object({
    connectionString: z.string().describe('MySQL connection string'),
    query: z.string().describe('SQL query to execute'),
  }),
  description: 'Executes SQL queries against a MySQL database',
  execute: async inputData => {
    const { connectionString, query } = inputData;
    let connection: mysql.Connection | null = null;

    try {
      console.log('🔌 Connecting to MySQL for query execution...');
      connection = await createDatabaseConnection(connectionString);
      console.log('✅ Connected to MySQL for query execution');

      validateQuery(query);

      const result = await executeQuery(connection, query);

      return {
        success: true,
        data: result,
        rowCount: result.length,
        executedQuery: query,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        executedQuery: query,
      };
    } finally {
      if (connection) {
        await connection.end();
      }
    }
  },
});
