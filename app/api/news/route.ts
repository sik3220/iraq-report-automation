import Database from "better-sqlite3";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  const dbPath = path.join(process.cwd(), "data", "articles.db");
  const db = new Database(dbPath, { readonly: true });

  try {
    const articles = db
      .prepare(
        `
        SELECT *
        FROM articles
        ORDER BY collected_at DESC
        `
      )
      .all();

    return Response.json({
      success: true,
      count: articles.length,
      articles,
    });
  } finally {
    db.close();
  }
}