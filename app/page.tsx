"use client";

import { useEffect, useMemo, useState } from "react";
import { groupArticles, reportingSources } from "./article-groups";
import { normalizeReportLine, summaryLines } from "./report-format";
import { createReport } from "./report-export";

type Article = {
  id: number;
  category: "정치" | "안보" | "주택" | "경제" | "세계" | "NIC";
  source: string;
  date: string;
  title: string;
  originalTitle: string;
  revision: number;
  summary: string[];
  original: string;
};

type JobRun = { job: "collection" | "analysis"; status: "running" | "success" | "failed"; started_at: string; finished_at: string | null; last_success: string | null; detail: string | null };
type DashboardMeta = { analysisBudget?: {usedUsd:number; monthlyUsd:number; blocked:boolean; time:string} | null; reportPeriod: { start: string; end: string }; summary: Record<string, number>; testDataCount: number; sources: Array<{ source_id: string; name: string; status: string; note: string | null; checked_at: string | null; counts: Record<string, number> }>; operations?: JobRun[] };
type ApiArticle = {
  id: number;
  category: Article["category"];
  source: string;
  published_at: string | null;
  report_date: string | null;
  title: string;
  ai_title: string | null;
  edit_revision: number;
  summary: string | null;
  original: string;
};

const getDisplayTitle = (article: Pick<Article, "title" | "originalTitle">) =>
  normalizeReportLine(article.title) || article.originalTitle.trim();

const sourceStatusLabel = (status: string) => ({
  ok: "정상", disabled: "비활성", stale: "오래된 피드", unchecked: "미확인",
  metadata: "목록 정상", error: "연결 오류",
})[status] || "확인 필요";

const sourceStatusStyle = (status: string) => {
  if (status === "ok" || status === "metadata") return "bg-green-100 text-green-800";
  if (status === "disabled" || status === "unchecked") {
    return "bg-slate-200 text-slate-700";
  }
  return "bg-amber-100 text-amber-800";
};

const runTime = (value: string | null) => value ? new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Baghdad", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
}).format(new Date(value)) : "기록 없음";

type BodyRequest = { id: number; title: string; source: string; url: string; report_date: string; edit_revision: number };
export default function Home() {
  const [needsBody, setNeedsBody] = useState<BodyRequest[]>([]);
  const [bodyArticle, setBodyArticle] = useState<BodyRequest | null>(null);
  const [bodyText, setBodyText] = useState("");
  const [bodyError, setBodyError] = useState("");
  const [bodySaving, setBodySaving] = useState(false);
  async function saveBody() {
    if (!bodyArticle || bodySaving) return;
    setBodySaving(true); setBodyError("");
    try {
      const response = await fetch("/api/news", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "provide_body", id: bodyArticle.id, expectedRevision: bodyArticle.edit_revision, body: bodyText }), signal: AbortSignal.timeout(15000) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "저장 실패");
      setBodyArticle(null); setBodyText(""); retryLoad();
    } catch (error) { setBodyError(error instanceof Error ? error.message : "저장 실패"); }
    finally { setBodySaving(false); }
  }
  const [periodView, setPeriodView] = useState("current");
  const [articles, setArticles] = useState<Article[]>([]);
  const [dashboardMeta, setDashboardMeta] = useState<DashboardMeta | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [authRequired, setAuthRequired] = useState(false);
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadArticles() {
      try {
        const response = await fetch(`/api/news?period=${periodView}`, { signal: controller.signal });
        if (response.status === 401) {
          setAuthRequired(true);
          return;
        }
        if (!response.ok) throw new Error("Failed to load articles");

        const data = await response.json();
        if (!data.success || !Array.isArray(data.articles)) {
          throw new Error("Invalid articles response");
        }

        const nextArticles = data.articles.map((article: ApiArticle) => ({
          id: article.id,
          category: article.category,
          source: article.source,
          date: article.report_date || "게시일 미확인",
          title: normalizeReportLine(article.ai_title || "") || article.title,
          originalTitle: article.title,
          revision: article.edit_revision,
          summary: article.summary
            ? summaryLines(article.summary)
            : [],
          original: article.original,
        }));

        if (!controller.signal.aborted) {
          setArticles(nextArticles);
          setDashboardMeta(data.meta || null);
          setNeedsBody(data.needsBody || []);
        }
      } catch {
        if (!controller.signal.aborted) {
          setLoadError("기사를 불러오지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.");
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }

    void loadArticles();
    return () => controller.abort();
  }, [loadAttempt, periodView]);

  const retryLoad = () => {
    setIsLoading(true);
    setLoadError(null);
    setLoadAttempt((attempt) => attempt + 1);
  };

  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("전체");

  const [originalArticle, setOriginalArticle] = useState<Article | null>(null);
  const [editingArticle, setEditingArticle] = useState<Article | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSummary, setEditSummary] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  const articleGroups = useMemo(() => groupArticles(articles), [articles]);
  const filteredArticles = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();

    return articleGroups.filter((group) => group.some((article) => {
      const matchesCategory =
        selectedCategory === "전체" ||
        article.category === selectedCategory;

      const searchableText = [
        article.title,
        article.originalTitle,
        article.source,
        article.category,
        ...article.summary,
      ]
        .join(" ")
        .toLowerCase();

      const matchesSearch = !keyword || searchableText.includes(keyword);

      return matchesCategory && matchesSearch;
    }));
  }, [articleGroups, searchTerm, selectedCategory]);

  const categoryCounts = useMemo(() => {
    return {
      전체: articleGroups.length,
      정치: articleGroups.filter(([article]) => article.category === "정치").length,
      안보: articleGroups.filter(([article]) => article.category === "안보").length,
      주택: articleGroups.filter(([article]) => article.category === "주택").length,
      경제: articleGroups.filter(([article]) => article.category === "경제").length,
      세계: articleGroups.filter(([article]) => article.category === "세계").length,
      NIC: articleGroups.filter(([article]) => article.category === "NIC").length,
      선택: selectedIds.length,
    };
  }, [articleGroups, selectedIds]);

  const toggleArticle = (id: number) => {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((selectedId) => selectedId !== id)
        : [...current, id],
    );
  };

  const openEdit = (article: Article) => {
    setSaveError(null);
    setSaveNotice(null);
    setEditingArticle(article);
    setEditTitle(getDisplayTitle(article));
    setEditSummary(article.summary.join("\n"));
  };

  const saveEdit = async () => {
    if (!editingArticle || isSaving) return;
    const title = normalizeReportLine(editTitle);
    if (!title) {
      setSaveError("제목을 입력해 주세요.");
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`/api/news?period=${periodView}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          id: editingArticle.id,
          title,
          summary: summaryLines(editSummary).join("\n"),
          expectedRevision: editingArticle.revision,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        setSaveError(typeof data.error === "string" ? data.error : "저장하지 못했습니다. 다시 시도해 주세요.");
        return;
      }
      const saved = data.article;
      setArticles((current) => current.map((article) =>
        article.id === saved.id
          ? { ...article, title: saved.ai_title, summary: summaryLines(saved.summary), revision: saved.edit_revision }
          : article
      ));
      setEditingArticle(null);
      setSaveNotice("수정 내용을 저장했습니다. 새로고침 후에도 유지됩니다.");
    } catch {
      setSaveError("저장 결과를 확인하지 못했습니다. 입력 내용을 복사해 두고 다시 시도하거나 새로고침해 주세요.");
    } finally {
      clearTimeout(timeout);
      setIsSaving(false);
    }
  };
  const [isGenerating, setIsGenerating] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const generateWord = async () => {
    if (isGenerating) return;
    setIsGenerating(true); setExportError(null);
    try {
      const response = await fetch("/report-template.docx");
      if (!response.ok) throw new Error("보고서 서식을 불러오지 못했습니다.");
      const result = await createReport(articles.filter(article => selectedIds.includes(article.id)), await response.arrayBuffer());
      const blob = new Blob([new Uint8Array(result.data)], {type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url; anchor.download = result.filename;
      window.document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Word 파일을 생성하지 못했습니다. 다시 시도해 주세요.");
    } finally { setIsGenerating(false); }
  };

  async function login() {
    if (isLoggingIn) return;
    setIsLoggingIn(true); setLoginError("");
    try {
      const response = await fetch("/api/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: loginPassword }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "로그인에 실패했습니다.");
      setLoginPassword(""); setAuthRequired(false); retryLoad();
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "로그인에 실패했습니다.");
    } finally { setIsLoggingIn(false); }
  }

  if (authRequired) return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-6">
      <form className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm" onSubmit={(event) => { event.preventDefault(); void login(); }}>
        <h1 className="text-xl font-bold text-slate-900">주간정보보고 자동화</h1>
        <p className="mt-2 text-sm text-slate-600">대시보드 비밀번호를 입력해 주세요.</p>
        <label className="mt-5 block text-sm font-semibold" htmlFor="dashboard-password">비밀번호</label>
        <input id="dashboard-password" type="password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2" autoFocus />
        {loginError && <p className="mt-2 text-sm text-red-700" role="alert">{loginError}</p>}
        <button type="submit" disabled={isLoggingIn || !loginPassword} className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{isLoggingIn ? "확인 중..." : "로그인"}</button>
      </form>
    </main>
  );

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 rounded-xl bg-slate-900 px-6 py-5 text-white">
          <h1 className="text-2xl font-bold">주간정보보고 자동화</h1>
          <p className="mt-1 text-sm text-slate-300">
            Iraq Weekly Intelligence Report Automation
          </p>
        </header>

        {dashboardMeta && (
          <section className="mb-6 space-y-4">
            <div className="rounded-xl border border-blue-200 bg-blue-50 px-5 py-4"><p className="text-xs font-semibold text-blue-700">현재 보고 기간</p><p className="mt-1 text-lg font-bold text-blue-950">{dashboardMeta.reportPeriod.start} ~ {dashboardMeta.reportPeriod.end}</p><p className="mt-1 text-xs text-blue-800">목요일~수요일 · 바그다드 시간 기준</p></div>
            <div className="grid gap-3 md:grid-cols-4">{[["이번 주 후보 기사", dashboardMeta.summary.included || 0], ["분석 대기", dashboardMeta.summary.pending || 0], ["본문·출처 확인 대기", dashboardMeta.summary.review || 0], ["제외·중복", (dashboardMeta.summary.excluded || 0) + (dashboardMeta.summary.duplicate || 0)]].map(([label, count]) => <div key={label} className="rounded-lg border border-slate-200 bg-white px-4 py-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-bold">{count}</p></div>)}</div>
            {dashboardMeta.analysisBudget && <p className="text-sm text-slate-600">
              매일 {dashboardMeta.analysisBudget.time} 자동 분석(바그다드) · 이번 달 예상 비용 {"$"}{dashboardMeta.analysisBudget.usedUsd.toFixed(2)} / {"$"}{dashboardMeta.analysisBudget.monthlyUsd.toFixed(2)}
              {dashboardMeta.analysisBudget.blocked && " · 예산 잔액 부족: 남은 기사는 분석 대기"}
            </p>}
            <div className="grid gap-3 md:grid-cols-2">
              {["collection", "analysis"].map((job) => {
                const run = dashboardMeta.operations?.find((item) => item.job === job);
                const healthy = run?.status === "success";
                return <div key={job} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
                  <div className="flex items-center justify-between"><span className="font-semibold">{job === "collection" ? "기사 수집" : "후보 분석"}</span><span className={`rounded px-2 py-1 text-xs ${healthy ? "bg-green-100 text-green-800" : run?.status === "running" ? "bg-blue-100 text-blue-800" : "bg-amber-100 text-amber-800"}`}>{healthy ? "정상" : run?.status === "running" ? "실행 중" : run ? "확인 필요" : "기록 없음"}</span></div>
                  <p className="mt-2 text-xs text-slate-600">마지막 정상 실행: {runTime(run?.last_success || null)}{run?.status === "failed" && run.detail ? ` · ${run.detail}` : ""}</p>
                </div>;
              })}
            </div>
            {dashboardMeta.testDataCount > 0 && <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">확인된 시험 기사 {dashboardMeta.testDataCount}건(test.com)은 제외 상태입니다. 실제 출처에서 시험 수집한 기사와는 구분됩니다.</p>}
            <details className="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <summary className="cursor-pointer text-sm font-semibold">출처 수집 상태 · {dashboardMeta.sources.length}개</summary>
              <div className="mt-3 flex flex-wrap gap-2">
                {dashboardMeta.sources.map((source) => (
                  <details key={source.source_id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <summary className="cursor-pointer list-none whitespace-nowrap">
                      <span className="mr-2 font-medium">{source.name}</span>
                      <span className={`rounded px-2 py-1 text-xs ${sourceStatusStyle(source.status)}`}>
                        {sourceStatusLabel(source.status)}
                      </span>
                    </summary>
                    <div className="mt-3 max-w-sm border-t border-slate-200 pt-2 text-xs leading-5 text-slate-600">
                      {source.note && <p>{source.note}</p>}
                      <p>{source.checked_at ? `마지막 확인: ${source.checked_at}` : "수집 확인 기록 없음"}</p>
                      {Object.keys(source.counts).length > 0 && (
                        <p>수집 결과: {Object.entries(source.counts).map(([key, count]) => `${key} ${count}`).join(" · ")}</p>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </details>
          </section>
        )}

        <details className="mb-6 rounded-xl border border-amber-200 bg-white p-4">
          <summary className="cursor-pointer font-semibold">원문 자동 처리 현황</summary>
          <p className="my-3 text-sm text-slate-600">제목만 확보된 출처나 자동 본문 확보에 실패한 기사가 포함된 수입니다. 원문이 확보된 기사는 분석 대기로 이동하고, 끝까지 확보하지 못한 중요 기사만 직접 확인할 수 있습니다.</p>
          {needsBody.map((item) => <div key={item.id} className="border-t py-3">
            <p className="text-xs text-slate-500">{item.source} · {item.report_date}</p>
            <p className="my-1 font-medium">{item.title}</p>
            {/^https?:\/\//.test(item.url) && <a href={item.url} target="_blank" rel="noopener noreferrer" className="mr-4 text-sm text-blue-700">기사 링크 열기</a>}
            <button className="rounded border px-3 py-1 text-sm" onClick={() => { setBodyArticle(item); setBodyText(""); setBodyError(""); }}>본문 붙여 넣기</button>
          </div>)}
        </details>

        <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-8">
          {Object.entries(categoryCounts).map(([label, count]) => (
            <div
              key={label}
              className="rounded-lg border border-slate-200 bg-white px-4 py-3"
            >
              <p className="text-xs text-slate-500">{label}</p>
              <p className="mt-1 text-xl font-bold">{count}</p>
            </div>
          ))}
        </section>

        <div className="mb-4 flex gap-3">
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="제목·출처·요약 검색"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />

          <select
            value={selectedCategory}
            onChange={(event) => setSelectedCategory(event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500"
          >
            <option value="전체">전체</option>
            <option value="정치">정치</option>
            <option value="안보">안보</option>
            <option value="주택">주택</option>
            <option value="경제">경제</option>
            <option value="세계">세계</option>
            <option value="NIC">NIC</option>
          </select>
        </div>

        {saveNotice && (
          <p role="status" className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
            {saveNotice}
          </p>
        )}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="flex gap-2" aria-label="기사 기간 선택">
          {[['current', '이번 주 기사'], ['archive', '지난 기사']].map(([value, label]) => (
            <button key={value} aria-pressed={periodView === value} onClick={() => {
              if (periodView === value) return;
              setIsLoading(true); setLoadError(null); setArticles([]); setSelectedIds([]); setPeriodView(value);
            }} className={`rounded-lg px-4 py-2 text-sm ${periodView === value ? 'bg-slate-900 text-white' : 'bg-white border border-slate-300'}`}>{label}</button>
          ))}
          </div>
          <button
            onClick={generateWord}
            disabled={selectedIds.length === 0 || isGenerating}
            className="ml-auto whitespace-nowrap rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isGenerating ? "Word 생성 중…" : `선택 기사 ${selectedIds.length}건 Word 생성`}
          </button>
        </div>
        {exportError && <p role="alert" className="mb-3 text-sm text-red-700">{exportError}</p>}
        <h2 className="mb-3 text-lg font-bold">{periodView === 'current' ? '이번 주 보고서 후보' : '지난 보고서 후보'}</h2>
        <section className="space-y-3" aria-label="기사 목록" aria-busy={isLoading}>
          {isLoading && (
            <p role="status" className="rounded-xl bg-white p-6 text-sm text-slate-600">
              기사를 불러오는 중입니다…
            </p>
          )}
          {loadError && (
            <div role="alert" className="rounded-xl border border-red-200 bg-white p-6">
              <p className="text-sm text-red-700">{loadError}</p>
              <button
                type="button"
                onClick={retryLoad}
                className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm text-white"
              >
                다시 시도
              </button>
            </div>
          )}
          {!isLoading && !loadError && filteredArticles.length === 0 && (
            <p role="status" className="rounded-xl bg-white p-6 text-sm text-slate-600">
              {articles.length === 0
                ? (periodView === "current" && (dashboardMeta?.summary.pending || 0) > 0 ? `이번 주 ${dashboardMeta?.summary.pending}건이 분석 대기 중입니다. 분석·선정 완료 후 후보가 표시됩니다.` : "해당 기간의 보고서 후보가 없습니다.")
                : "검색 조건에 맞는 기사가 없습니다. 검색어 또는 분류를 변경해 주세요."}
            </p>
          )}
          {articles.length > articleGroups.length && <p className="text-sm text-slate-600">후보 {articles.length}건을 {articleGroups.length}개 기사 묶음으로 표시 · 펼쳐서 매체별 내용 확인·선택 가능</p>}
          {filteredArticles.map((group) => {
            const article = group[0];
            const sources = reportingSources(group);
            const isSelected = selectedIds.includes(article.id);
            const displayTitle = getDisplayTitle(article);


            return (
              <article
                key={article.id}
                className={`rounded-xl border bg-white p-4 ${
                  isSelected
                    ? "border-blue-500 ring-1 ring-blue-200"
                    : "border-slate-200"
                }`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    aria-label={`${displayTitle} 선택`}
                    onChange={() => toggleArticle(article.id)}
                    className="mt-1 h-4 w-4"
                  />

                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="rounded bg-slate-100 px-2 py-1">
                        {article.category}
                      </span>
                      <span>{article.source}</span>
                      <span>{article.date}</span>
                    </div>

                    <h2 className="text-base font-semibold">{displayTitle}</h2>
                    {group.length > 1 && <details className="mt-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm">
                      <summary className="cursor-pointer font-medium text-blue-800">{sources.length}개 언론사 보도{group.slice(1).some(item => selectedIds.includes(item.id)) ? " · 추가 기사 선택됨" : ""}</summary>
                      <p className="mt-2 text-xs text-slate-600">{sources.join(" · ")} · 유사 제목 기준 묶음이며 독립 검증을 뜻하지 않습니다</p>
                      {group.map(item => <div key={item.id} className="mt-3 border-t border-blue-100 pt-2">
                        <label className="flex items-start gap-2">
                          <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleArticle(item.id)} className="mt-1" />
                          <span><span className="text-xs text-slate-500">{item.source} · {item.date}</span><br />{getDisplayTitle(item)}</span>
                        </label>
                        {item.summary.map((line, index) => <p key={index} className="mt-1 text-xs leading-5 text-slate-700">{line}</p>)}
                        <div className="mt-2 flex gap-3 text-xs text-blue-800">
                          <button onClick={() => setOriginalArticle(item)}>원문보기</button>
                          <button onClick={() => openEdit(item)}>편집</button>
                        </div>
                      </div>)}
                    </details>}


                    {article.summary.length > 0 && (
                    <div className="mt-3 rounded-lg bg-slate-50 px-4 py-3">
                      {article.summary.map((line, index) => (
                        <p
                          key={`${article.id}-${index}`}
                          className="text-sm leading-6 text-slate-700"
                        >
                          {line}
                        </p>
                      ))}
                    </div>
                    )}

                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => setOriginalArticle(article)}
                        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
                      >
                        원문보기
                      </button>

                      <button
                        onClick={() => openEdit(article)}
                        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
                      >
                        편집
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </section>


      </div>

      {bodyArticle && <div role="dialog" aria-modal="true" aria-label="기사 본문 입력" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="w-full max-w-3xl rounded-xl bg-white p-6">
          <h2 className="mb-3 font-bold">{bodyArticle.title}</h2>
          <label htmlFor="article-body" className="text-sm">원문 본문 (100~100,000자)</label>
          <textarea id="article-body" rows={12} maxLength={100000} disabled={bodySaving} value={bodyText} onChange={event => setBodyText(event.target.value)} className="mt-2 w-full rounded border p-3" />
          {bodyError && <p role="alert" className="text-red-700">{bodyError}</p>}
          <div className="mt-3 flex justify-end gap-3"><button disabled={bodySaving} onClick={() => setBodyArticle(null)}>취소</button><button disabled={bodySaving || bodyText.trim().length < 100} onClick={saveBody} className="rounded bg-blue-700 px-4 py-2 text-white disabled:opacity-50">{bodySaving ? "저장 중…" : "저장 · 분석 대기로 이동"}</button></div>
        </div>
      </div>}
      {originalArticle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs text-slate-500">
                  {originalArticle.source} · {originalArticle.date}
                </p>
                <h2 className="mt-1 text-lg font-bold">
                  {getDisplayTitle(originalArticle)}
                </h2>

              </div>

              <button
                onClick={() => setOriginalArticle(null)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                닫기
              </button>
            </div>

            <div className="whitespace-pre-wrap rounded-lg bg-slate-100 p-4 text-sm leading-7">
              {originalArticle.original}
            </div>
          </div>
        </div>
      )}

      {editingArticle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-3xl rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">기사 편집</h2>

            <label htmlFor="edit-title" className="mb-2 block text-sm font-semibold">제목</label>
            <input
              id="edit-title"
              disabled={isSaving}
              maxLength={200}
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500"
            />

            <label htmlFor="edit-summary" className="mb-2 block text-sm font-semibold">
              보고서 반영 문안
            </label>
            <textarea
              id="edit-summary"
              disabled={isSaving}
              maxLength={10000}
              value={editSummary}
              onChange={(event) => setEditSummary(event.target.value)}
              rows={8}
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm leading-7 outline-none focus:border-blue-500"
              placeholder="* 사실 내용&#10;☞ 전망·분석·시사점"
            />

            <p className="mt-2 text-xs text-slate-500">
              각 줄 앞에 * 또는 ☞를 입력하면 해당 기호가 그대로 Word에
              반영됩니다.
            </p>

            {saveError && (
              <p role="alert" className="mt-3 text-sm text-red-700">{saveError}</p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                disabled={isSaving}
                onClick={() => setEditingArticle(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm"
              >
                취소
              </button>

              <button
                disabled={isSaving}
                onClick={saveEdit}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
              >
                {isSaving ? "저장 중…" : "저장"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}


