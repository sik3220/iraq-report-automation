"use client";

import { useEffect, useMemo, useState } from "react";
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
  summary: string[];
  original: string;
};


export default function Home() {
  const [articles, setArticles] = useState<Article[]>([]);
  useEffect(() => {
    async function loadArticles() {
      const response = await fetch("/api/news");
      const data = await response.json();
  
      setArticles(
        data.articles.map((article: any) => ({
          id: article.id,
          category: article.category,
          source: article.source,
          date: article.published_at
            ? article.published_at.slice(0, 10)
            : "",
          title: article.title,
          summary: article.summary
            ? article.summary.split("\n").filter(Boolean)
            : [],
          original: article.original,
        }))
      );
    }
  
    loadArticles();
  }, []);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("전체");

  const [originalArticle, setOriginalArticle] = useState<Article | null>(null);
  const [editingArticle, setEditingArticle] = useState<Article | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSummary, setEditSummary] = useState("");

  const filteredArticles = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();

    return articles.filter((article) => {
      const matchesCategory =
        selectedCategory === "전체" ||
        article.category === selectedCategory;

      const searchableText = [
        article.title,
        article.source,
        article.category,
        ...article.summary,
      ]
        .join(" ")
        .toLowerCase();

      const matchesSearch =
        !keyword || searchableText.includes(keyword);

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
    setEditingArticle(article);
    setEditTitle(article.title);
    setEditSummary(article.summary.join("\n"));
  };

  const saveEdit = () => {
    if (!editingArticle) return;

    const newSummary = editSummary
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    setArticles((current) =>
      current.map((article) =>
        article.id === editingArticle.id
          ? {
              ...article,
              title: editTitle.trim(),
              summary: newSummary,
            }
          : article,
      ),
    );

    setEditingArticle(null);
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
              text: article.title,
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

        <section className="space-y-3">
          {filteredArticles.map((article) => {
            const isSelected = selectedIds.includes(article.id);

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

                    <h2 className="text-base font-semibold">
                      {article.title}
                    </h2>

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
                  {originalArticle.title}
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

            <label className="mb-2 block text-sm font-semibold">제목</label>
            <input
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500"
            />

            <label className="mb-2 block text-sm font-semibold">
              보고서 반영 문안
            </label>
            <textarea
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

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setEditingArticle(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm"
              >
                취소
              </button>

              <button
                onClick={saveEdit}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
              >
                저장
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}