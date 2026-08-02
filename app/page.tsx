"use client";

import { useMemo, useState } from "react";

type Article = {
  id: number;
  category: "정치" | "안보" | "경제";
  source: string;
  date: string;
  title: string;
  summary: string[];
};

const articles: Article[] = [
  {
    id: 1,
    category: "정치",
    source: "Shafaq News",
    date: "2026.08.02",
    title: "8.2, Al-Zaidi 총리, 남은 장관 인선 관련 협의 지속",
    summary: [
      "시아조정기구와 남은 장관 후보자 확정을 위한 협의를 이어가고 있다고 발표",
      "향후 2주 내 신임투표를 실시할 가능성이 제기",
    ],
  },
  {
    id: 2,
    category: "안보",
    source: "Iraqi PMO",
    date: "2026.08.02",
    title: "8.2, 이라크 보안당국, 불법 드론 제조시설 단속 강화",
    summary: [
      "Baghdad 외곽에서 무장단체 관련 시설을 수색하고 드론 장비를 압수",
    ],
  },
  {
    id: 3,
    category: "경제",
    source: "Reuters",
    date: "2026.08.02",
    title: "8.2, 국제유가, 중동 긴장 완화 기대감으로 소폭 하락",
    summary: [
      "호르무즈 해협 통항 정상화 기대가 커지며 브렌트유와 WTI가 동반 하락",
    ],
  },
];

export default function Home() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("전체");
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
  }, [searchTerm, selectedCategory]);
  const categoryCounts = useMemo(() => {
    return {
      전체: articles.length,
      정치: articles.filter((article) => article.category === "정치").length,
      안보: articles.filter((article) => article.category === "안보").length,
      경제: articles.filter((article) => article.category === "경제").length,
      선택: selectedIds.length,
    };
  }, [selectedIds]);

  const toggleArticle = (id: number) => {
    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((selectedId) => selectedId !== id)
        : [...current, id],
    );
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

        <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
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
    <option value="경제">경제</option>
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

                    <h2 className="text-base font-semibold">{article.title}</h2>

                    <div className="mt-3 rounded-lg bg-slate-50 px-4 py-3">
                      {article.summary.map((line) => (
                        <p
                          key={line}
                          className="text-sm leading-6 text-slate-700"
                        >
                          * {line}
                        </p>
                      ))}
                    </div>

                    <div className="mt-3 flex gap-2">
                      <button className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50">
                        원문 보기
                      </button>
                      <button className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50">
                        수정
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
            disabled={selectedIds.length === 0}
            className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            선택 기사 {selectedIds.length}건 Word 생성
          </button>
        </div>
      </div>
    </main>
  );
}