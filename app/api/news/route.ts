import Database from "better-sqlite3";
import path from "path";
import { normalizeReportLine, summaryLines } from "../../report-format";

export const dynamic = "force-dynamic";

export async function GET() {
  const dbPath = path.join(process.cwd(), "data", "articles.db");
  let db: Database.Database | undefined;
  try {
    db = new Database(dbPath, { readonly: true });
    const articles = db.prepare(
      `SELECT id, category, source, title,
        COALESCE(edited_title, ai_title) AS ai_title,
        COALESCE(edited_summary, summary) AS summary,
        edit_revision, original, published_at, collected_at, url
       FROM articles WHERE report_status = 'included'
       ORDER BY collected_at DESC`
    ).all();
    return Response.json({ success: true, count: articles.length, articles });
  } catch (error) {
    console.error("Failed to load articles:", error);
    return Response.json(
      { success: false, error: "기사를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." },
      { status: 500 },
    );
  } finally {
    db?.close();
  }
}

export async function PATCH(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ success: false, error: "허용되지 않은 요청입니다." }, { status: 403 });
  }
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return Response.json({ success: false, error: "JSON 형식으로 요청해 주세요." }, { status: 415 });
  }

  let input;
  try {
    input = await request.json();
  } catch {
    return Response.json({ success: false, error: "저장 요청을 읽지 못했습니다." }, { status: 400 });
  }
  if (
    !input || typeof input !== "object" ||
    !Number.isSafeInteger(input.id) || input.id < 1 ||
    !Number.isSafeInteger(input.expectedRevision) || input.expectedRevision < 0 ||
    typeof input.title !== "string" || input.title.length > 200 ||
    typeof input.summary !== "string" || input.summary.length > 10000
  ) {
    return Response.json(
      { success: false, error: "입력 내용을 확인해 주세요. 제목은 200자, 추가 내용은 10,000자까지 저장할 수 있습니다." },
      { status: 400 },
    );
  }

  const title = normalizeReportLine(input.title);
  const summary = summaryLines(input.summary).join("\n");
  if (!title) {
    return Response.json({ success: false, error: "제목을 입력해 주세요." }, { status: 400 });
  }

  let db: Database.Database | undefined;
  try {
    db = new Database(path.join(process.cwd(), "data", "articles.db"), { fileMustExist: true });
    // Separate overrides preserve the source/AI text and survive AI reprocessing.
    const article = db.prepare(
      `UPDATE articles
       SET edited_title = ?, edited_summary = ?, edit_revision = edit_revision + 1
       WHERE id = ? AND report_status = 'included' AND edit_revision = ?
       RETURNING id, edited_title AS ai_title, edited_summary AS summary, edit_revision`
    ).get(title, summary, input.id, input.expectedRevision);

    if (!article) {
      const exists = db.prepare(
        "SELECT id FROM articles WHERE id = ? AND report_status = 'included'"
      ).get(input.id);
      return Response.json(
        {
          success: false,
          error: exists
            ? "다른 화면에서 먼저 수정한 기사입니다. 입력 내용을 복사한 뒤 새로고침하여 최신 문안을 확인해 주세요."
            : "저장할 보고서 후보 기사를 찾을 수 없습니다.",
        },
        { status: exists ? 409 : 404 },
      );
    }
    return Response.json({ success: true, article });
  } catch (error) {
    console.error("Failed to save article:", error);
    return Response.json(
      { success: false, error: "저장하지 못했습니다. 입력 내용은 유지됩니다. 잠시 후 다시 시도해 주세요." },
      { status: 500 },
    );
  } finally {
    db?.close();
  }
}
