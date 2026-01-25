import mysql from 'mysql2/promise';

async function showSchema() {
  let conn;
  try {
    console.log('🔌 Connecting to MySQL database...');
    conn = await mysql.createConnection({
      host: '161.97.142.217',
      port: 13306,
      user: 'tnea_admin',
      password: 'M3ER8MfzddLDjPdf',
      database: 'tnea',
      waitForConnections: true,
      connectionLimit: 10,
      queueLimit: 0,
    });

    console.log('✅ Connected!\n');

    const [tables] = await conn.query('SHOW TABLES');
    console.log('📋 Tables in database:');
    for (const row of tables) {
      const tableName = Object.values(row)[0];
      console.log(`  - ${tableName}`);
    }

    console.log('\n📊 --- DETAILED SCHEMA ---\n');

    for (const row of tables) {
      const tableName = Object.values(row)[0];
      console.log(`📌 ${tableName}:`);
      const [cols] = await conn.query(`DESCRIBE ${tableName}`);
      for (const col of cols) {
        const pk = col.Key === 'PRI' ? ' [PRIMARY KEY]' : '';
        console.log(`  • ${col.Field}: ${col.Type}${pk}`);
      }
      const [count] = await conn.query(`SELECT COUNT(*) as cnt FROM ${tableName}`);
      console.log(`  → ${count[0].cnt} rows\n`);
    }

    await conn.end();
    console.log('✅ Database introspection complete!');
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

showSchema();
