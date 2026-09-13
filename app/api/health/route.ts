import Database from "better-sqlite3";
import path from "path";

export const dynamic = "force-dynamic";

export function GET() {
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
