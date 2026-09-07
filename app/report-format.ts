export function normalizeReportLine(line: string): string {
  return line.trim().replace(/[.。]+(?=[”’"')\]]*$)/u, "").trim();
}

export function summaryLines(summary: string): string[] {
  return summary.split("\n").map(normalizeReportLine).filter(Boolean);
}
