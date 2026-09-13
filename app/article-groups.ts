type Candidate = { id: number; title: string; date: string; source: string; originalTitle?: string };

function eventText(title: string) {
  return title.normalize("NFKC").toLowerCase()
    .replace(/미 중부사령부|미 중동사령부|미군|미국군/g, "미국")
    .replace(/원유운반선|원유 유조선/g, "유조선")
    .replace(/영해/g, "해역")
    .replace(/공격|타격/g, "공격")
    .replace(/\birgc\b|이란 혁명수비대/g, "혁명수비대")
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function combinedText(article: Candidate) {
  return [article.title, article.originalTitle || ""].join(" ");
}

const genericEventWords = new Set(["이라크", "이란", "미국", "정부", "당국", "관계자", "장관", "발표", "논의", "관련", "지역", "국가", "안보", "상황", "문제", "대응", "공식", "새로운"]);

function semanticTokens(article: Candidate) {
  const text = combinedText(article).normalize("NFKC").toLowerCase()
    .replace(/미 중부사령부|미 중동사령부|미군|미국군/g, "미국")
    .replace(/원유운반선|원유 유조선/g, "유조선")
    .replace(/공격|타격|공습/g, "공격");
  return new Set((text.match(/[\p{L}\p{N}]+/gu) || []).filter(token => token.length >= 2 && !genericEventWords.has(token)));
}

function sameSemanticEvent(a: Candidate, b: Candidate) {
  const left = semanticTokens(a), right = semanticTokens(b);
  const shared = [...left].filter(token => right.has(token));
  if (shared.length < 2 || !shared.some(token => token.length >= 4 || /\d/.test(token))) return false;
  return shared.length / Math.min(left.size, right.size) >= 0.5;
}
function sameSecurityStrike(a: Candidate, b: Candidate) {
  const left = combinedText(a), right = combinedText(b);
  const isIsis = (text: string) => /\bisis\b|\bis\b|داعش|이슬람국가|테러조직/.test(text.toLowerCase());
  const isDiyala = (text: string) => /diyala|디얄라|ديالى/.test(text.toLowerCase());
  const isAirstrike = (text: string) => /f[- ]?16|공군|공습|airstrike|air ?strike|은신처|hideout|미사일|missile/.test(text.toLowerCase());
  return isIsis(left) && isIsis(right) && isDiyala(left) && isDiyala(right) && isAirstrike(left) && isAirstrike(right);
}

export function sameEvent(a: Candidate, b: Candidate) {
  // ponytail: conservative headline heuristic; add reviewed event IDs if ambiguous matches become common.
  if (!/^\d{4}-\d{2}-\d{2}$/.test(a.date) || a.date !== b.date) return false;
  const left = eventText(a.title), right = eventText(b.title);
  if (Math.min(left.length, right.length) < 12) return false;
  if ((a.title.match(/\d+(?:[.,]\d+)*/g) || []).join("|") !== (b.title.match(/\d+(?:[.,]\d+)*/g) || []).join("|")) return false;
  if (/부인|반박|철회|취소|미확인|아니|않|없/.test(left) !== /부인|반박|철회|취소|미확인|아니|않|없/.test(right)) return false;
  if (sameSecurityStrike(a, b)) return true;
  if (sameSemanticEvent(a, b)) return true;
  const pairs = (text: string) => new Set(Array.from({ length: text.length - 1 }, (_, i) => text.slice(i, i + 2)));
  const x = pairs(left), y = pairs(right);
  const common = [...x].filter(pair => y.has(pair)).length;
  return 2 * common / (x.size + y.size) >= 0.72;
}

export function groupArticles<T extends Candidate>(articles: T[]): T[][] {
  const groups: T[][] = [];
  // ponytail: quadratic comparison fits weekly candidate lists; index by date if volume grows.
  for (const article of [...articles].sort((a, b) => a.id - b.id)) {
    const group = groups.find(items => items.every(item => sameEvent(item, article)));
    if (group) group.push(article);
    else groups.push([article]);
  }
  const order = new Map(articles.map((article, index) => [article.id, index]));
  return groups.sort((a, b) => Math.min(...a.map(item => order.get(item.id)!)) - Math.min(...b.map(item => order.get(item.id)!)));
}

export function reportingSources(articles: Candidate[]) {
  return [...new Map(articles.map(article => [article.source.trim().toLowerCase(), article.source.trim()])).values()];
}
