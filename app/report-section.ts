export type ReportSection = "politics" | "security" | "oil" | "economy" | "conflict" | "world";
type Candidate = { category: string; title: string; originalTitle: string; summary: string[] };

export function reportSection(article: Candidate): ReportSection {
  const title = article.title || article.originalTitle;
  const domestic = /이라크|바그다드|Baghdad|Basra|Erbil|Suleimaniyah|Nineveh|쿠르드|쿠르디스탄|페쉬메르가|인민동원군|PMF|Al-Nujaba/i.test(title);
  const regional = /이란|이스라엘|호르무즈|홍해|후티|사우디|레바논|예멘|가자|美|미국|Trump|혁명수비대/i.test(title);
  const incident = /공격|피격|공습|테러|총격|폭발|암살|납치|드론|미사일|체포|격추|무기 반납|무장해제|무장단체|무장세력|보복|시위/.test(title);
  const policy = /내각|국회|의회|법안|국정|정당|인선|장관직|최고사령관실|정부 구성|감사|청렴위원회|NIC|비스마야|Bismayah|건설주택부/i.test(title);
  // ponytail: headline-led rules avoid moving an incident because its background mentions oil prices.
  if (/유가|원유 가격|원유가격|브렌트|WTI|두바이유|바스라.*유|국제유가/.test(title) && /상승|하락|급등|급락|보합|달러|최고|최저|가격|근접/.test(title)) return "oil";
  if (domestic && incident && !/美·사우디|미국·사우디/.test(title) && !policy) return "security";
  if (policy && (domestic || article.category !== "세계")) return "politics";
  if (regional && /공격|공습|미사일|군사|협상|휴전|봉쇄|통항|제재|보복|분쟁|전쟁|경고|나포|핵시설/.test(title) && !domestic) return "conflict";
  if (article.category === "세계") return regional ? "conflict" : "world";
  if (article.category === "안보") return "security";
  if (["정치", "주택", "NIC"].includes(article.category)) return "politics";
  return "economy";
}

export function refineReportLine(line: string): string {
  return line.trim()
    .replace(/\b(?:Al-)?(Halbousi|Maliki|Sudani)\b/gi, (_match, name: string) => `Al-${name[0].toUpperCase()}${name.slice(1).toLowerCase()}`)
    .replace(/ 전 총리/g, " 前 총리")
    .replace(/(발표|강조|지시|확인|부인|취소|추진|체결|논의|제기|시사|경고|합의)(?:했다고|했다고 한다|했다|하였음|했음|함)([.。]*)$/, "$1")
    .replace(/[.。]+(?=[”’"')\]]*$)/u, "").trim();
}
