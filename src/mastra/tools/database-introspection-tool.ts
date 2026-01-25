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
    const [rows] = await connection.execute(query);
    return rows as any[];
  } catch (error) {
    throw new Error(`Failed to execute query: ${error instanceof Error ? error.message : String(error)}`);
  }
};

export const databaseIntrospectionTool = createTool({
  id: 'database-introspection',
  inputSchema: z.object({
    connectionString: z.string().describe('MySQL connection string'),
  }),
  description: 'Introspects a MySQL database to understand its schema, tables, columns, and relationships',
  execute: async inputData => {
    const { connectionString } = inputData;
    let connection: mysql.Connection | null = null;

    try {
      console.log('🔌 Connecting to MySQL for introspection...');
      connection = await createDatabaseConnection(connectionString);
      console.log('✅ Connected to MySQL for introspection');

      // Get current database name
      const [dbResult] = await connection.execute('SELECT DATABASE() as db_name');
      const currentDb = (dbResult as any[])[0]?.db_name;

      // Get all tables
      const tablesQuery = `
        SELECT
          TABLE_SCHEMA as schema_name,
          TABLE_NAME as table_name,
          TABLE_TYPE as table_type
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = ?
        ORDER BY TABLE_SCHEMA, TABLE_NAME;
      `;

      const [tables] = await connection.execute(tablesQuery, [currentDb]);

      // Get detailed column information for each table
      const columnsQuery = `
        SELECT
          TABLE_SCHEMA as table_schema,
          TABLE_NAME as table_name,
          COLUMN_NAME as column_name,
          DATA_TYPE as data_type,
          CHARACTER_MAXIMUM_LENGTH as character_maximum_length,
          NUMERIC_PRECISION as numeric_precision,
          NUMERIC_SCALE as numeric_scale,
          IS_NULLABLE as is_nullable,
          COLUMN_DEFAULT as column_default,
          COLUMN_KEY as column_key,
          CASE WHEN COLUMN_KEY = 'PRI' THEN true ELSE false END as is_primary_key
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = ?
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
      `;

      const [columns] = await connection.execute(columnsQuery, [currentDb]);

      // Get foreign key relationships
      const relationshipsQuery = `
        SELECT
          kcu.TABLE_SCHEMA as table_schema,
          kcu.TABLE_NAME as table_name,
          kcu.COLUMN_NAME as column_name,
          kcu.REFERENCED_TABLE_SCHEMA as foreign_table_schema,
          kcu.REFERENCED_TABLE_NAME as foreign_table_name,
          kcu.REFERENCED_COLUMN_NAME as foreign_column_name,
          kcu.CONSTRAINT_NAME as constraint_name
        FROM information_schema.KEY_COLUMN_USAGE kcu
        WHERE kcu.TABLE_SCHEMA = ?
          AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY kcu.TABLE_SCHEMA, kcu.TABLE_NAME, kcu.COLUMN_NAME;
      `;

      const [relationships] = await connection.execute(relationshipsQuery, [currentDb]);

      // Get indexes
      const indexesQuery = `
        SELECT
          TABLE_SCHEMA as schema_name,
          TABLE_NAME as table_name,
          INDEX_NAME as index_name,
          COLUMN_NAME as column_name,
          NON_UNIQUE as non_unique,
          SEQ_IN_INDEX as seq_in_index
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = ?
        ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
      `;

      const [indexes] = await connection.execute(indexesQuery, [currentDb]);

      // Get table row counts
      const rowCountsPromises = (tables as any[]).map(async table => {
        try {
          const countQuery = `SELECT COUNT(*) as row_count FROM \`${table.table_name}\`;`;
          const result = await executeQuery(connection!, countQuery);
          return {
            schema_name: table.schema_name,
            table_name: table.table_name,
            row_count: parseInt(result[0].row_count),
          };
        } catch (error) {
          return {
            schema_name: table.schema_name,
            table_name: table.table_name,
            row_count: 0,
            error: error instanceof Error ? error.message : String(error),
          };
        }
      });

      const rowCounts = await Promise.all(rowCountsPromises);

      return {
        tables,
        columns,
        relationships,
        indexes,
        rowCounts,
        summary: {
          total_tables: (tables as any[]).length,
          total_columns: (columns as any[]).length,
          total_relationships: (relationships as any[]).length,
          total_indexes: (indexes as any[]).length,
        },
      };
    } catch (error) {
      throw new Error(`Failed to introspect database: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      if (connection) {
        await connection.end();
      }
    }
  },
});
