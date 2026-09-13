import { convertToXmlComponent, ImportedXmlComponent, patchDocument, PatchType, TextRun, type FileChild } from "docx";
import patterns from "./report-patterns.json";
import { reportSection, refineReportLine } from "./report-section";
import { normalizeReportLine } from "./report-format";

type ReportArticle = { id: number; category: string; date: string; title: string; originalTitle: string; summary: string[]; revision?: number };
type XmlNode = { type: string; name?: string; text?: string; attributes?: Record<string, string | undefined>; elements?: XmlNode[] };

function fill(pattern: XmlNode, text: string): XmlNode {
  const copy: XmlNode = { ...pattern };
  if (copy.text === "__TEXT__") copy.text = text;
  if (copy.elements) copy.elements = copy.elements.map(child => fill(child, text));
  return copy;
}

function paragraph(node: XmlNode): FileChild {
  const component = convertToXmlComponent(node as Parameters<typeof convertToXmlComponent>[0]);
  if (!(component instanceof ImportedXmlComponent)) throw new Error("보고서 문단 서식을 읽지 못했습니다.");
  return Object.assign(component, { fileChild: Symbol() });
}

function parseDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("게시일을 확인할 수 없는 기사가 있습니다.");
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.valueOf()) || date.toISOString().slice(0, 10) !== value) throw new Error("기사 날짜를 확인해 주세요.");
  return date;
}

export function reportPeriod(articles: ReportArticle[]) {
  if (!articles.length) throw new Error("보고서에 넣을 기사를 선택해 주세요.");
  const starts = articles.map(article => {
    const date = parseDate(article.date);
    date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 3) % 7);
    return date.toISOString().slice(0, 10);
  });
  if (new Set(starts).size !== 1) throw new Error("서로 다른 보고 주간의 기사가 선택됐습니다. 목~수 기준 한 주의 기사를 선택해 주세요.");
  const end = parseDate(starts[0]); end.setUTCDate(end.getUTCDate() + 6);
  const issue = new Date(end); issue.setUTCDate(issue.getUTCDate() + 1);
  return { start: starts[0], end: end.toISOString().slice(0, 10), issue: issue.toISOString().slice(0, 10) };
}

export async function createReport(articles: ReportArticle[], template: ArrayBuffer | Uint8Array) {
  const period = reportPeriod(articles);
  const sorted = [...articles].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  const allowed = ["정치", "안보", "주택", "경제", "세계", "NIC"];
  if (sorted.some(article => !allowed.includes(article.category))) throw new Error("기사 분류를 확인해 주세요.");
  const children: FileChild[] = [];
  const heading = (kind: "section" | "subsection" | "topic", text: string) => children.push(paragraph(fill(patterns[kind], text)));
  const addArticles = (items: ReportArticle[]) => items.forEach(article => {
    const clean = article.revision ? normalizeReportLine : refineReportLine;
    const title = clean(article.title) || article.originalTitle.trim();
    const [, month, day] = article.date.split("-").map(Number);
    const node = fill(patterns.article, `${month}.${day}, ${title}`);
    node.elements!.find(element => element.name === "w:pPr")!.elements!.unshift({type:"element",name:"w:keepLines"});
    for (const line of article.summary) {
      const marker = line.trim().startsWith("☞") ? "☞" : "*";
      const text = clean(line.replace(/^\s*[*•☞]\s*/, ""));
      if (!text) continue;
      node.elements!.push({type:"element",name:"w:r",elements:[{type:"element",name:"w:br"}]}, fill(patterns.detail, `${marker} ${text}`));
    }
    children.push(paragraph(node));
  });
  const sections: Partial<Record<ReturnType<typeof reportSection>, ReportArticle[]>> = {};
  for (const article of sorted) (sections[reportSection(article)] ??= []).push(article);
  const add = (key: ReturnType<typeof reportSection>, label: string) => {
    const items = sections[key];
    if (items?.length) { heading("topic", label); addArticles(items); }
  };
  if (sections.politics || sections.security || sections.oil || sections.economy) {
    heading("section", "이라크 국내 상황");
    if (sections.politics || sections.security) {
      heading("subsection", "정국 / 치안");
      add("politics", "정치권 동향");
      add("security", "이라크 주간 테러 상황");
    }
    if (sections.oil || sections.economy) {
      heading("subsection", "경제");
      add("oil", "국제유가 관련 동향");
      add("economy", "기타 경제 동향");
    }
  }
  if (sections.conflict || sections.world) {
    heading("section", "국제사회");
    add("conflict", "美·이스라엘-이란 분쟁 관련");
    add("world", "기타 국제사회 동향");
  }
  const short = (value: string) => { const [year, month, day] = value.split("-").map(Number); return `΄${String(year).slice(-2)}.${month}.${day}`; };
  const [year, month, day] = period.issue.split("-").map(Number);
  const data = await patchDocument({
    outputType: "uint8array", data: template, keepOriginalStyles: true, recursive: false,
    patches: {
      period: { type: PatchType.PARAGRAPH, children: [new TextRun(`(${short(period.start)} ~ ${short(period.end)})`)] },
      issueDate: { type: PatchType.PARAGRAPH, children: [new TextRun(`${year}. ${month}. ${day}.`)] },
      body: { type: PatchType.DOCUMENT, children },
    },
  });
  return { data, filename: `건설_이라크 주간 종합상황보고(${month}월 ${day}일).docx` };
}


