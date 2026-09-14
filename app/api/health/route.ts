import Database from "better-sqlite3";
import postgres from "postgres";
import path from "path";

export const dynamic = "force-dynamic";

const databaseUrl = process.env.DATABASE_URL;
const remoteDb = databaseUrl ? postgres(databaseUrl, { max: 1, prepare: false, ssl: "require" }) : null;

export async function GET() {
  if (remoteDb) {
    try {
      await remoteDb`SELECT 1`;
      return Response.json({ status: "ok", database: "supabase" });
    } catch {
      return Response.json({ status: "error", database: "unavailable" }, { status: 503 });
    }
  }
  const dbPath = path.join(process.cwd(), "data", "articles.db");
  let db: Database.Database | undefined;
  try {
    db = new Database(dbPath, { readonly: true, timeout: 30000 });
    db.prepare("SELECT 1").get();
    return Response.json({ status: "ok", database: "ok" });
  } catch {
    return Response.json({ status: "error", database: "unavailable" }, { status: 503 });
  } finally {
    db?.close();
  }
}
