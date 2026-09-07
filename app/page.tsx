"use client";

import { useEffect, useMemo, useState } from "react";
import { normalizeReportLine, summaryLines } from "./report-format";
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  AlignmentType,
} from "docx";

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

type ApiArticle = {
  id: number;
  category: Article["category"];
  source: string;
  published_at: string | null;
  title: string;
  ai_title: string | null;
  edit_revision: number;
  summary: string | null;
  original: string;
};

const getDisplayTitle = (article: Pick<Article, "title" | "originalTitle">) =>
  normalizeReportLine(article.title) || article.originalTitle.trim();

export default function Home() {
  const [articles, setArticles] = useState<Article[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadArticles() {
      try {
        const response = await fetch("/api/news", { signal: controller.signal });
        if (!response.ok) throw new Error("Failed to load articles");

        const data = await response.json();
        if (!data.success || !Array.isArray(data.articles)) {
          throw new Error("Invalid articles response");
        }

        const nextArticles = data.articles.map((article: ApiArticle) => ({
          id: article.id,
          category: article.category,
          source: article.source,
          date: article.published_at ? article.published_at.slice(0, 10) : "",
          title: normalizeReportLine(article.ai_title || "") || article.title,
          originalTitle: article.title,
          revision: article.edit_revision,
          summary: article.summary
            ? summaryLines(article.summary)
            : [],
          original: article.original,
        }));

        if (!controller.signal.aborted) setArticles(nextArticles);
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
  }, [loadAttempt]);

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

  const filteredArticles = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();

    return articles.filter((article) => {
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
    });
  }, [articles, searchTerm, selectedCategory]);

  const categoryCounts = useMemo(() => {
    return {
      전체: articles.length,
      정치: articles.filter((article) => article.category === "정치").length,
      안보: articles.filter((article) => article.category === "안보").length,
      주택: articles.filter((article) => article.category === "주택").length,
      경제: articles.filter((article) => article.category === "경제").length,
      세계: articles.filter((article) => article.category === "세계").length,
      NIC: articles.filter((article) => article.category === "NIC").length,
      선택: selectedIds.length,
    };
  }, [articles, selectedIds]);

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
      const response = await fetch("/api/news", {
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
  const generateWord = async () => {
    const selectedArticles = articles.filter((article) =>
      selectedIds.includes(article.id),
    );

    if (selectedArticles.length === 0) {
      return;
    }

    const children: Paragraph[] = [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 360 },
        children: [
          new TextRun({
            text: "주간정보보고",
            bold: true,
            size: 32,
          }),
        ],
      }),
    ];

    selectedArticles.forEach((article) => {
      children.push(
        new Paragraph({
          spacing: { before: 160, after: 100 },
          children: [
            new TextRun({
              text: getDisplayTitle(article),
              bold: true,
              size: 22,
            }),
          ],
        }),
      );

      article.summary.forEach((line) => {
        children.push(
          new Paragraph({
            spacing: { after: 80 },
            children: [
              new TextRun({
                text: line,
                size: 20,
              }),
            ],
          }),
        );
      });

      children.push(
        new Paragraph({
          spacing: { after: 200 },
          children: [new TextRun({ text: "" })],
        }),
      );
    });

    const document = new Document({
      sections: [
        {
          children,
        },
      ],
    });

    const blob = await Packer.toBlob(document);
    const url = URL.createObjectURL(blob);

    const anchor = documentGlobalCreateAnchor(url);
    anchor.click();

    URL.revokeObjectURL(url);
  };

  const documentGlobalCreateAnchor = (url: string) => {
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `주간정보보고_${new Date()
      .toISOString()
      .slice(0, 10)}.docx`;

    window.document.body.appendChild(anchor);

    anchor.addEventListener(
      "click",
      () => {
        window.document.body.removeChild(anchor);
      },
      { once: true },
    );

    return anchor;
  };

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 rounded-xl bg-slate-900 px-6 py-5 text-white">
          <h1 className="text-2xl font-bold">주간정보보고 자동화</h1>
          <p className="mt-1 text-sm text-slate-300">
            Iraq Weekly Intelligence Report Automation
          </p>
        </header>

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
                ? "선정 기준에 맞는 보고서 후보 기사가 없습니다."
                : "검색 조건에 맞는 기사가 없습니다. 검색어 또는 분류를 변경해 주세요."}
            </p>
          )}
          {filteredArticles.map((article) => {
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

        <div className="mt-6 flex justify-end">
          <button
            onClick={generateWord}
            disabled={selectedIds.length === 0}
            className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            선택 기사 {selectedIds.length}건 Word 생성
          </button>
        </div>
      </div>

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
