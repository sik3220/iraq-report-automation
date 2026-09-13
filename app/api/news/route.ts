import Database from "better-sqlite3";
import path from "path";
import fs from "node:fs";
import { normalizeReportLine, summaryLines } from "../../report-format";
import { isAuthenticated } from "../../lib/auth";

export const dynamic = "force-dynamic";

function currentReportWeek() {
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Baghdad", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const start = new Date(`${date}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 3) % 7);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

export async function GET(request: Request) {
  if (!isAuthenticated(request)) return Response.json({ success: false, error: "로그인이 필요합니다." }, { status: 401 });
  const dbPath = path.join(process.cwd(), "data", "articles.db");
  let db: Database.Database | undefined;
  try {
    db = new Database(dbPath, { readonly: true, timeout: 30000 });
    const period = currentReportWeek();
    const archive = new URL(request.url).searchParams.get("period") === "archive";
    const periodFilter = archive ? "week_start < ?" : "week_start = ?";
    const needsBody = db.prepare("SELECT id, source, title, url, report_date, edit_revision FROM articles WHERE report_status = 'review' AND COALESCE(original, '') = '' AND week_start = ? ORDER BY report_date DESC").all(period.start);
    const articles = db.prepare(
      `SELECT id, category, source, title,
        COALESCE(edited_title, ai_title) AS ai_title,
        COALESCE(edited_summary, summary) AS summary,
        edit_revision, original, published_at, report_date, collected_at, url
       FROM articles WHERE report_status = 'included' AND ${periodFilter}
       ORDER BY collected_at DESC`
    ).all(period.start);
    const summaryRows = db.prepare("SELECT report_status AS status, COUNT(*) AS count FROM articles WHERE week_start = ? GROUP BY report_status").all(period.start) as Array<{ status: string; count: number }>;
    const summary: Record<string, number> = {};
    summaryRows.forEach((row) => { summary[row.status] = row.count; });
    const testData = db.prepare("SELECT COUNT(*) AS count FROM articles WHERE url = 'https://test.com' AND report_status = 'excluded'").get() as { count: number };
    const sources = db.prepare<[], { source_id: string; name: string; status: string; note: string | null; checked_at: string | null; counts: string | null }>("SELECT source_id, name, status, note, checked_at, counts FROM source_checks ORDER BY name").all().map((row: { source_id: string; name: string; status: string; note: string | null; checked_at: string | null; counts: string | null }) => ({ ...row, counts: row.counts ? JSON.parse(row.counts) : {} }));
    const hasJobRuns = db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_runs'").get();
    const operations = hasJobRuns ? db.prepare(`
      SELECT r.job,r.status,r.started_at,r.finished_at,r.detail,
        (SELECT MAX(s.finished_at) FROM job_runs s WHERE s.job=r.job AND s.status='success') AS last_success
      FROM job_runs r WHERE r.id=(SELECT MAX(latest.id) FROM job_runs latest WHERE latest.job=r.job)
      ORDER BY r.job`).all() : [];
    let analysisBudget = null;
    const configPath = path.join(process.cwd(), "deploy", "analysis-settings.json");
    if (fs.existsSync(configPath) && db.prepare("SELECT 1 FROM sqlite_master WHERE name='ai_spend'").get()) {
      const settings = JSON.parse(fs.readFileSync(configPath, "utf8"));
      const day = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Baghdad",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
      const usage = db.prepare("SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) AS total FROM ai_spend WHERE substr(day,1,7)=?").get(day.slice(0,7)) as {total:number};
      const state = db.prepare("SELECT blocked FROM ai_budget_state WHERE day=?").get(day) as {blocked:number} | undefined;
      analysisBudget = { usedUsd: usage.total / 1000000, monthlyUsd: settings.monthly_usd,
        blocked: Boolean(state?.blocked), time: settings.time_baghdad };
    }
    return Response.json({ success: true, count: articles.length, articles, needsBody, meta: { reportPeriod: period, summary, testDataCount: testData.count, sources, operations, analysisBudget } });
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
  if (!isAuthenticated(request)) return Response.json({ success: false, error: "로그인이 필요합니다." }, { status: 401 });
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
  if (input?.action === "provide_body") {
    if (!Number.isSafeInteger(input.id) || input.id < 1 || !Number.isSafeInteger(input.expectedRevision) || input.expectedRevision < 0 || typeof input.body !== "string" || input.body.trim().length < 100 || input.body.length > 100000) {
      return Response.json({ success: false, error: "기사 본문을 100~100,000자로 입력해 주세요." }, { status: 400 });
    }
    const connection = new Database(path.join(process.cwd(), "data", "articles.db"), { fileMustExist: true, timeout: 30000 });
    try {
      const result = connection.prepare("UPDATE articles SET original = ?, report_status = 'pending', report_reason = '사용자 본문 입력 — 분석 대기', edit_revision = edit_revision + 1 WHERE id = ? AND edit_revision = ? AND report_status = 'review' AND COALESCE(original, '') = ''").run(input.body.trim(), input.id, input.expectedRevision);
      return Response.json({ success: result.changes === 1, error: result.changes ? undefined : "기사 상태가 변경됐습니다. 새로고침 후 확인해 주세요." }, { status: result.changes ? 200 : 409 });
    } finally { connection.close(); }
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
    db = new Database(path.join(process.cwd(), "data", "articles.db"), { fileMustExist: true, timeout: 30000 });
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






