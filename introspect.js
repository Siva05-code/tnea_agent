const mysql = require('mysql2/promise');

async function introspect() {
  let conn;
  try {
    conn = await mysql.createConnection({
      uri: 'mysql://tnea_admin:M3ER8MfzddLDjPdf@161.97.142.217:13306/tnea',
      connectTimeout: 30000,
    });

    const [dbResult] = await conn.execute('SELECT DATABASE() as db_name');
    const db = dbResult[0].db_name;
    console.log('📊 Database:', db);
    console.log('');

    const [tables] = await conn.execute(
      'SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME',
    );

    console.log('📋 TABLES AND COLUMNS:');
    console.log('======================\n');

    for (const t of tables) {
      const [cols] = await conn.execute(
        'SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION',
        [db, t.TABLE_NAME],
      );

      console.log(`📌 Table: ${t.TABLE_NAME}`);
      const [countResult] = await conn.execute(`SELECT COUNT(*) as cnt FROM \`${t.TABLE_NAME}\``);
      const count = countResult[0].cnt;
      console.log(`   Rows: ${count}\n`);

      for (const col of cols) {
        const pk = col.COLUMN_KEY === 'PRI' ? ' [PRIMARY KEY]' : '';
        const nullable = col.IS_NULLABLE === 'YES' ? '' : ' [NOT NULL]';
        console.log(`   • ${col.COLUMN_NAME}: ${col.DATA_TYPE}${pk}${nullable}`);
      }
      console.log('');
    }

    await conn.end();
    console.log('✅ Database introspection complete!');
  } catch (e) {
    console.error('❌ Error:', e.message);
  }
}

introspect();
