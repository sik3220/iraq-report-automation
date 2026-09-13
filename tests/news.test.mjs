import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import ts from "typescript";
import Database from "better-sqlite3";
import React from "react";

const loadCommonJs = createRequire(import.meta.url);
function compiled(file) {
  return ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
}
const formatting = {};
vm.runInNewContext(compiled("app/report-format.ts"), { exports: formatting });
const grouping = {};
vm.runInNewContext(compiled("app/article-groups.ts"), { exports: grouping });
const routeCode = compiled("app/api/news/route.ts");
const authStub = { isAuthenticated: () => true };

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "iraq-news-test-"));
  fs.mkdirSync(path.join(root, "data"));
  const dbPath = path.join(root, "data/articles.db");
  const db = new Database(dbPath);
  db.exec(`CREATE TABLE articles (
    id INTEGER PRIMARY KEY, category TEXT, source TEXT, title TEXT, ai_title TEXT,
    summary TEXT, original TEXT, published_at TEXT, collected_at TEXT, url TEXT,
    report_status TEXT, report_reason TEXT, report_date TEXT, week_start TEXT, edited_title TEXT, edited_summary TEXT,
    edit_revision INTEGER NOT NULL DEFAULT 0
  )`);
  db.prepare(`INSERT INTO articles(id,title,ai_title,summary,original,report_status)
    VALUES (?,?,?,?,?,?)`).run(1, "source title", "AI title", "* AI detail", "source body", "included");
  db.prepare("INSERT INTO articles(id,title,report_status) VALUES (2,'excluded','excluded')").run();
  db.exec("CREATE TABLE source_checks(source_id TEXT,name TEXT,status TEXT,note TEXT,checked_at TEXT,counts TEXT)");
  db.exec("CREATE TABLE job_runs(id INTEGER PRIMARY KEY,job TEXT,started_at TEXT,finished_at TEXT,status TEXT,detail TEXT)");
  db.prepare("INSERT INTO job_runs VALUES (1,'collection','2026-09-13T08:00:00+03:00','2026-09-13T08:01:00+03:00','success','')").run();
  const day = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Baghdad",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
  const start = new Date(`${day}T00:00:00Z`); start.setUTCDate(start.getUTCDate() - (start.getUTCDay()+3)%7);
  db.prepare("UPDATE articles SET week_start=?").run(start.toISOString().slice(0,10));
  db.close();
  t.after(() => {
    fs.unlinkSync(dbPath);
    fs.rmdirSync(path.join(root, "data"));
    fs.rmdirSync(root);
  });
  const exports = {};
  vm.runInNewContext(routeCode, {
    exports, require: name => name === "../../report-format" ? formatting : name === "../../lib/auth" ? authStub : loadCommonJs(name),
    process: { cwd: () => root }, Response, URL,
    console: { error() {} },
  });
  return { ...exports, dbPath };
}
function request(input, headers = {}) {
  return new Request("http://localhost:3100/api/news", {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(input),
  });
}
const edit = { id: 1, title: "Saved title.", summary: "* 3.14% increase.\n", expectedRevision: 0 };

test("edits survive a fresh connection and AI regeneration without changing source text", async t => {
  const api = fixture(t);
  assert.equal((await api.PATCH(request(edit))).status, 200);
  let data = await (await api.GET(new Request("http://localhost:3100/api/news"))).json();
  assert.equal(data.articles[0].ai_title, "Saved title");
  assert.equal(data.articles[0].summary, "* 3.14% increase");
  assert.equal(data.articles[0].edit_revision, 1);
  const db = new Database(api.dbPath);
  assert.equal(db.prepare("SELECT title FROM articles WHERE id=1").get().title, "source title");
  assert.equal(db.prepare("SELECT ai_title FROM articles WHERE id=1").get().ai_title, "AI title");
  db.prepare("UPDATE articles SET ai_title='regenerated', summary='regenerated' WHERE id=1").run();
  db.close();
  data = await (await api.GET(new Request("http://localhost:3100/api/news"))).json();
  assert.equal(data.articles[0].ai_title, "Saved title");
  assert.equal(data.articles[0].original, "source body");
  assert.equal(data.count, 1);
  assert.equal(data.meta.operations[0].job, "collection");
  assert.equal(data.meta.operations[0].status, "success");
});

test("stale edits cannot overwrite saved text; empty summary is a persistent override", async t => {
  const api = fixture(t);
  await api.PATCH(request(edit));
  assert.equal((await api.PATCH(request({ ...edit, title: "stale" }))).status, 409);
  const result = await api.PATCH(request({ ...edit, summary: "", expectedRevision: 1 }));
  assert.equal(result.status, 200);
  const data = await (await api.GET(new Request("http://localhost:3100/api/news"))).json();
  assert.equal(data.articles[0].summary, "");
  assert.equal(data.articles[0].edit_revision, 2);
});

test("invalid, unknown, excluded and cross-origin writes are rejected", async t => {
  const api = fixture(t);
  for (const input of [
    null, { ...edit, id: -1 }, { ...edit, expectedRevision: 0.5 },
    { ...edit, title: " ." }, { ...edit, title: "a".repeat(201) },
    { ...edit, summary: [] },
  ]) assert.equal((await api.PATCH(request(input))).status, 400);
  assert.equal((await api.PATCH(request({ ...edit, id: 999 }))).status, 404);
  assert.equal((await api.PATCH(request({ ...edit, id: 2 }))).status, 404);
  assert.equal((await api.PATCH(request(edit, { Origin: "https://other.example" }))).status, 403);
  assert.equal((await api.PATCH(request(edit, { "Content-Type": "text/plain" }))).status, 415);
  assert.equal((await api.PATCH(new Request("http://localhost:3100/api/news", {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: "{",
  }))).status, 400);
  assert.equal((await (await api.GET(new Request("http://localhost:3100/api/news"))).json()).articles[0].edit_revision, 0);
});

test("a database failure is reported instead of claiming the edit was saved", async t => {
  const api = fixture(t);
  const db = new Database(api.dbPath);
  db.exec("DROP TABLE articles");
  db.close();
  assert.equal((await api.PATCH(request(edit))).status, 500);
});

test("normalization preserves decimals and removes only terminal periods", () => {
  assert.equal(formatting.normalizeReportLine("* 3.14%."), "* 3.14%");
  assert.equal(formatting.normalizeReportLine('* "text."'), '* "text"');
});
function findElement(tree, predicate) {
  if (!tree || typeof tree !== "object") return undefined;
  if (predicate(tree)) return tree;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const found = findElement(child, predicate);
    if (found) return found;
  }
}
function editor(fetch) {
  const article = {
    id: 1, category: "NIC", source: "test", date: "", title: "AI title",
    originalTitle: "source", original: "body", summary: ["* detail"], revision: 0,
  };
  const state = [[], null, "", "", false, "current", [article], null, false];
  let index = 0;
  const exports = {};
  vm.runInNewContext(compiled("app/page.tsx"), {
    exports, fetch, AbortController, setTimeout, clearTimeout,
    require: name => name === "./report-export" ? {} : name === "./article-groups" ? grouping : name === "./report-format" ? formatting : name === "react" ? {
      ...React, useEffect() {}, useMemo: fn => fn(),
      useState(initial) {
        const slot = index++;
        if (!(slot in state)) state[slot] = initial;
        return [state[slot], value => { state[slot] = typeof value === "function" ? value(state[slot]) : value; }];
      },
    } : loadCommonJs(name),
  });
  const render = () => { index = 0; return exports.default(); };
  const find = predicate => findElement(render(), predicate);
  // Open the real edit handler on the rendered article card.
  const editButton = find(e => e.type === "button" && e.props.onClick && e.props.children !== undefined &&
    String(e.props.children).includes("편집"));
  editButton.props.onClick();
  find(e => e.props?.id === "edit-title").props.onChange({ target: { value: "Manual title." } });
  find(e => e.props?.id === "edit-summary").props.onChange({ target: { value: "* Manual detail." } });
  return { find };
}
const saveButton = e => e.type === "button" && e.props.children === "저장";

test("editor disables duplicate input while saving and updates the card after success", async () => {
  let complete;
  let payload;
  const ui = editor((_url, options) => {
    payload = JSON.parse(options.body);
    return new Promise(resolve => { complete = resolve; });
  });
  const saving = ui.find(saveButton).props.onClick();
  assert.equal(ui.find(e => e.props?.id === "edit-title").props.disabled, true);
  assert.equal(payload.expectedRevision, 0);
  assert.equal(payload.title, "Manual title");
  assert.equal(payload.summary, "* Manual detail");
  complete(Response.json({ success: true, article: {
    id: 1, ai_title: payload.title, summary: payload.summary, edit_revision: 1,
  } }));
  await saving;
  assert.equal(ui.find(e => e.props?.id === "edit-title"), undefined);
  assert.ok(ui.find(e => e.type === "h2" && e.props.children === "Manual title"));
  assert.ok(ui.find(e => e.props?.role === "status"));
});

test("editor preserves draft text and stays open after a save failure", async () => {
  const ui = editor(async () => Response.json({ success: false, error: "disk unavailable" }, { status: 500 }));
  await ui.find(saveButton).props.onClick();
  assert.equal(ui.find(e => e.props?.id === "edit-title").props.value, "Manual title.");
  assert.equal(ui.find(e => e.props?.id === "edit-summary").props.value, "* Manual detail.");
  assert.equal(ui.find(saveButton).props.disabled, false);
  assert.equal(ui.find(e => e.props?.role === "alert").props.children, "disk unavailable");
});
 test("manual body enters pending once and rejects short input or overwrite", async t => {
  const api = fixture(t);
  const db = new Database(api.dbPath);
  db.prepare("INSERT INTO articles(id,title,report_status,original) VALUES (3,'Reuters article','review','')").run(); db.close();
  const payload = {action:"provide_body",id:3,expectedRevision:0,body:"x"};
  assert.equal((await api.PATCH(request(payload))).status,400);
  payload.body = "Verified article body. ".repeat(10);
  assert.equal((await api.PATCH(request(payload))).status,200);
  assert.equal((await api.PATCH(request(payload))).status,409);
  const check = new Database(api.dbPath);
  const row=check.prepare("SELECT original,report_status FROM articles WHERE id=3").get(); check.close();
  assert.equal(row.original,payload.body.trim()); assert.equal(row.report_status,"pending");
 });


test("event groups preserve updates, count distinct outlets and avoid topic chaining", () => {
  const item = (id, title, source = "INA", date = "2026-09-09") => ({id, title, source, date});
  const a = item(1, "미 중부사령부, 이란 유조선 5척 파괴 발표");
  const b = item(2, "미군, 이란 원유 유조선 5척 파괴 발표", "Alsumaria");
  const c = item(3, b.title, "Alsumaria");
  const groups = grouping.groupArticles([c,b,a]);
  assert.equal(groups.length,1);
  assert.equal(groups[0][0].id,1);
  assert.equal(grouping.reportingSources(groups[0]).length,2);
  assert.equal(grouping.sameEvent(a,item(4,a.title.replace("5척","6척"))),false);
  assert.equal(grouping.sameEvent(a,item(5,a.title,"INA","2026-09-10")),false);
  assert.equal(grouping.sameEvent(a,item(6,a.title + " 부인")),false);
  assert.equal(grouping.sameEvent(a,item(7,"이란, 호르무즈 통항 제한·대미 미사일 경고")),false);
  assert.equal(grouping.sameEvent(a,item(8,a.title,"INA","게시일 미확인")),false);
  assert.equal(grouping.groupArticles([a,b,item(9,"이라크 항만공사, 호르무즈 폐쇄 대응책 논의")]).length,2);
});
