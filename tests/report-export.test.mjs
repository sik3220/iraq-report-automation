import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import ts from "typescript";
import * as docx from "docx";
const require = createRequire(import.meta.url);
const JSZip = createRequire(require.resolve("docx"))("jszip");
const compile = file => ts.transpileModule(fs.readFileSync(file, "utf8"), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText;
const format={}, exporter={}, sections={};
vm.runInNewContext(compile("app/report-section.ts"),{exports:sections});
vm.runInNewContext(compile("app/report-format.ts"),{exports:format});
vm.runInNewContext(compile("app/report-export.ts"),{exports:exporter,require:name=>name==="./report-section"?sections:name==="docx"?docx:name==="./report-format"?format:JSON.parse(fs.readFileSync("app/report-patterns.json","utf8"))});
const article=(id,category,date,title,summary=[])=>({id,category,date,title,originalTitle:"original",summary});
const template=fs.readFileSync("public/report-template.docx");
test("reference formatting, chronological selected content, escaping and report dates survive export",async()=>{
 const items=[article(3,"세계","2026-09-09","후속 <발표> & 검토.",["* 3.14% 상승."]),article(2,"정치","2026-09-09","수정한 제목"),article(1,"정치","2026-09-03","첫 기사")];
 const {data,filename}=await exporter.createReport(items,template);
 assert.equal(filename,"건설_이라크 주간 종합상황보고(9월 10일).docx");
 const zip=await JSZip.loadAsync(data), base=await JSZip.loadAsync(template);
 const xml=await zip.file("word/document.xml").async("string");
 assert.ok(xml.indexOf("첫 기사")<xml.indexOf("수정한 제목"));
 assert.ok(xml.indexOf("수정한 제목")<xml.indexOf("후속 &lt;발표&gt; &amp; 검토"));
 assert.match(xml,/΄26\.9\.3 ~ ΄26\.9\.9/);
 assert.match(xml,/2026\. 9\. 10\./);
 assert.match(xml,/\* 3\.14% 상승</);
 assert.doesNotMatch(xml,/\{\{|__TEXT__|9\.0,|내일 작성 예정|000|<undefined/);
 assert.match(xml,/w:w="11906"/);assert.match(xml,/w:h="16838"/);
 for(const name of ["word/numbering.xml","word/styles.xml","word/footer1.xml","word/theme/theme1.xml","word/fontTable.xml"]){
  assert.equal(await zip.file(name).async("string"),await base.file(name).async("string"),name);
 }
 assert.equal(Object.keys(zip.files).some(name=>name.startsWith("customXml/")),false);
 assert.equal(items[0].id,3);
});
test("empty or mixed report weeks and invalid dates cannot silently create a mislabeled report",async()=>{
 assert.throws(()=>exporter.reportPeriod([]));
 assert.throws(()=>exporter.reportPeriod([article(1,"정치","2026-09-09","a"),article(2,"세계","2026-09-10","b")]));
 assert.throws(()=>exporter.reportPeriod([article(1,"정치","2026-02-30","a")]));
 assert.throws(()=>exporter.reportPeriod([article(1,"정치","게시일 미확인","a")]));
 const p=exporter.reportPeriod([article(1,"세계","2026-01-01","제목")]);
 assert.equal(p.start,"2026-01-01");assert.equal(p.issue,"2026-01-08");
 const result=await exporter.createReport([article(1,"세계","2026-09-09","하나의 기사")],template);
 const zip=await JSZip.loadAsync(result.data);const xml=await zip.file("word/document.xml").async("string");
 assert.doesNotMatch(xml,/이라크 국내 상황|경제·에너지/);assert.match(xml,/국제사회/);
});


test("report sections follow the four reference reports and keep reactions intact", async () => {
 const cases = [
  ["경제", "이라크 영해 외국 유조선, 드론 피격", "security"],
  ["경제", "이라크 내각, 해외출장 중단·예산 60% 삭감", "politics"],
  ["NIC", "NIC 의장, 비스마야 사업 자금조달 논의", "politics"],
  ["세계", "미국·이란 협상 진전에 국제유가 5% 하락", "oil"],
  ["경제", "후티 반군, 사우디 석유시설 공격", "conflict"],
  ["세계", "미국, 이란 유조선 5척 공격", "conflict"],
  ["경제", "이라크, OPEC+ 일산 600만 배럴 요구", "economy"],
 ];
 const items = cases.map(([category,title,expected],i)=>{
  const item=article(i+1,category,"2026-09-09",title,["☞ 당국, 공격 주장을 부인했다고 발표"]);
  assert.equal(sections.reportSection(item),expected,title); return item;
 });
 const result=await exporter.createReport(items,template);
 const zip=await JSZip.loadAsync(result.data);const xml=await zip.file("word/document.xml").async("string");
 for(const title of ["정치권 동향","이라크 주간 테러 상황","국제유가 관련 동향","美·이스라엘-이란 분쟁 관련"])assert.ok(xml.includes(title));
 assert.match(xml,/☞ 당국/);assert.doesNotMatch(xml,/\* ☞/);
 assert.equal(sections.refineReportLine("Maliki 前 총리, 합의 가능성을 부인했다."),"Al-Maliki 前 총리, 합의 가능성을 부인");
 assert.equal(sections.refineReportLine("최소 3.14% 상승 가능성"),"최소 3.14% 상승 가능성");
});
