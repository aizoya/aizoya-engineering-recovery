/**
 * Read-only MongoDB client for the organizer Atlas cluster.
 *
 * The connection URI is read from Modelence config (_system.mongodbUri),
 * which is injected server-side from Modelence Cloud environment secrets.
 * It is never sent to the browser.
 *
 * This client is read-only by convention: no write operations are performed
 * in this presenter. All writes remain in the Python engineering workflow.
 */
import { getConfig } from 'modelence/server';
import { MongoClient } from 'mongodb';

let client: MongoClient | null = null;
let currentUri = '';

export async function getMongoClient(): Promise<MongoClient> {
  const uri = getConfig('_system.mongodbUri') as string;
  if (!client || currentUri !== uri) {
    if (client) {
      try { await client.close(); } catch (_) { /* ignore */ }
    }
    client = new MongoClient(uri, {
      appName: 'AIZOYA-Presenter',
      tls: true,
      serverSelectionTimeoutMS: 8000,
      connectTimeoutMS: 8000,
    });
    await client.connect();
    currentUri = uri;
  }
  return client;
}

export async function getAizoyadb() {
  // Database name matches the organizer sandbox: aizoya_recovery
  const c = await getMongoClient();
  return c.db('aizoya_recovery');
}

process.on('SIGTERM', async () => { if (client) await client.close(); });
process.on('SIGINT',  async () => { if (client) await client.close(); });
