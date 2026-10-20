// Builds the Independent Project report (.docx) from the Markdown-like sources in ../report/.
// Usage: run build_all.py (figures, this script, then the table-of-contents update), or
//        node docs/independent-project/scripts/build_report.js <output.docx>
//
// Source syntax: "# / ## / ###" headings, blank-line separated paragraphs, "- " bullets,
// **bold**, *italic*, `code`, and directives:
//   @section prelim|main          start the roman / arabic page-numbered part
//   @list Figure|Table            list of figures / tables (Word field)
//   @toc                          table of contents (Word field)
//   @acronyms                     "TERM | meaning" lines until a blank line
//   @table Caption {#tab:key}     pipe rows (first row = header) until a blank line
//   @figure path | Caption {#fig:key}
//   @eq text                      centred equation line
//   @references                   one APA reference per line until a blank line
//   [[fig:key]] / [[tab:key]]     cross-reference ("Figure 3" / "Table 2")

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, LineRuleType, Document, Footer, HeadingLevel, ImageRun, LevelFormat, NumberFormat,
  Packer, PageBreak, PageNumber, Paragraph, ShadingType, SimpleField, Table, TableCell, TableOfContents,
  TableRow, TextRun, WidthType,
} = require("docx");

const ROOT = path.resolve(__dirname, "../../..");
const SRC = path.resolve(__dirname, "../report");
const OUT = process.argv[2] || path.resolve(__dirname, "../WaterTracker_IP_2026_report.docx");

const FONT = "Times New Roman";
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1440;          // A4, 1-inch margins
const TEXT_W = PAGE_W - 2 * MARGIN;                            // 9026 DXA
const MAX_IMG_PX = 590;                                        // ≈ 6.15 in at 96 px/in
const MAX_IMG_H_PX = 420;                                      // ≈ 4.4 in, keeps square figures compact

// ------------------------------------------------------------------ cover page data
const COVER = {
  institution: "TamTam Digital School",
  logo: "[Insert Institution Logo]",
  title: "WaterTracker: Satellite Monitoring and Short-Term Forecasting of Small Reservoirs around Ouagadougou to Support Dry-Season Water Decisions",
  student: "[Student Full Name]",
  program: "[Academic Program]",
  supervisor: "[Supervisor Name]",
  year: "2026",
  date: "[Submission Date]",
};

// ------------------------------------------------------------------ helpers
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

function inline(text, base = {}) {
  // **bold**, *italic*, `code`
  const runs = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) runs.push(new TextRun({ text: tok.slice(2, -2), bold: true, ...base }));
    else if (tok.startsWith("`")) runs.push(new TextRun({ text: tok.slice(1, -1), font: "Consolas", size: 20, ...base }));
    else runs.push(new TextRun({ text: tok.slice(1, -1), italics: true, ...base }));
    last = m.index + tok.length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  return runs;
}

function stripLabel(s) {
  const m = s.match(/\s*\{#((?:fig|tab):[\w-]+)\}\s*$/);
  return m ? { text: s.slice(0, m.index).trim(), key: m[1] } : { text: s.trim(), key: null };
}

const thin = { style: BorderStyle.SINGLE, size: 4, color: "8A8984" };
const borders = { top: thin, bottom: thin, left: thin, right: thin, insideHorizontal: thin, insideVertical: thin };

function columnWidths(rows) {
  const n = rows[0].length;
  const len = Array.from({ length: n }, (_, j) => Math.max(...rows.map((r) => Math.min((r[j] || "").length, 60)), 6));
  // a column is never narrower than its longest word (header words are bold, hence the margin)
  const word = Array.from({ length: n }, (_, j) => Math.max(...rows.map((r) => Math.max(...(r[j] || "").split(/\s+/).map((t) => t.length)))));
  const total = len.reduce((a, b) => a + b, 0);
  const w = len.map((l, j) => Math.max(900, word[j] * 125 + 260, Math.round((l / total) * TEXT_W)));
  const diff = TEXT_W - w.reduce((a, b) => a + b, 0);
  w[w.indexOf(Math.max(...w))] += diff;
  return w;
}

function makeTable(rows, opts = {}) {
  const widths = opts.widths || columnWidths(rows);
  return new Table({
    width: { size: TEXT_W, type: WidthType.DXA },
    columnWidths: widths,
    borders: opts.borders === false ? undefined : borders,
    rows: rows.map((cells, i) => new TableRow({
      tableHeader: i === 0 && opts.header !== false,
      children: cells.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        shading: i === 0 && opts.header !== false ? { type: ShadingType.CLEAR, color: "auto", fill: "DCE6F2" } : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({
          style: "TableText",
          children: inline(c.trim(), i === 0 && opts.header !== false ? { bold: true } : {}),
        })],
      })),
    })),
  });
}

// ------------------------------------------------------------------ parse sources
const files = fs.readdirSync(SRC).filter((f) => f.endsWith(".md")).sort();
const lines = files.flatMap((f) => fs.readFileSync(path.join(SRC, f), "utf8").split(/\r?\n/).concat([""]));

// first pass: numbering of figures and tables
const labels = {};
let nf = 0, nt = 0;
for (const ln of lines) {
  if (ln.startsWith("@figure ")) { nf += 1; const { key } = stripLabel(ln.split("|").slice(1).join("|")); if (key) labels[key] = `Figure ${nf}`; }
  if (ln.startsWith("@table ")) { nt += 1; const { key } = stripLabel(ln.slice(7)); if (key) labels[key] = `Table ${nt}`; }
}
const resolve = (s) => s.replace(/\[\[((?:fig|tab):[\w-]+)\]\]/g, (_, k) => {
  if (!labels[k]) throw new Error(`unknown reference ${k}`);
  return labels[k];
});

const sections = { prelim: [], main: [] };
let current = null;
let figN = 0, tabN = 0;
let i = 0;
const out = () => sections[current];

function captionPara(kind, n, text) {
  return new Paragraph({
    style: "Caption",
    keepNext: kind === "Table",
    children: [new TextRun({ text: `${kind} `, bold: true }), new SimpleField(`SEQ ${kind} \\* ARABIC`, String(n)),
      new TextRun({ text: ": ", bold: true }), ...inline(text)],
  });
}

while (i < lines.length) {
  const raw = lines[i];
  const ln = resolve(raw);
  if (ln.startsWith("@section ")) { current = ln.slice(9).trim(); i += 1; continue; }
  if (!ln.trim()) { i += 1; continue; }
  if (current === null) throw new Error("content before @section");

  if (ln.startsWith("# ")) {
    out().push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(ln.slice(2))] }));
  } else if (ln.startsWith("## ")) {
    out().push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(ln.slice(3))] }));
  } else if (ln.startsWith("### ")) {
    out().push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(ln.slice(4))] }));
  } else if (ln.startsWith("@list ")) {
    const kind = ln.slice(6).trim();
    out().push(new TableOfContents(`List of ${kind}s`, { hyperlink: true, captionLabelIncludingNumbers: kind }));
  } else if (ln.startsWith("@toc")) {
    out().push(new Paragraph({ style: "TocTitle", pageBreakBefore: true, children: [new TextRun("Table of Contents")] }));
    out().push(new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }));
  } else if (ln.startsWith("@acronyms")) {
    const rows = [];
    i += 1;
    while (i < lines.length && lines[i].trim()) { rows.push(lines[i].split("|").map((s) => s.trim())); i += 1; }
    out().push(makeTable([["Acronym", "Meaning"], ...rows], { widths: [1700, TEXT_W - 1700] }));
    continue;
  } else if (ln.startsWith("@table ")) {
    const { text } = stripLabel(ln.slice(7));
    tabN += 1;
    const rows = [];
    i += 1;
    while (i < lines.length && lines[i].trim()) { rows.push(resolve(lines[i]).split("|")); i += 1; }
    out().push(captionPara("Table", tabN, text));
    out().push(makeTable(rows));
    out().push(new Paragraph({ style: "AfterTable", children: [] }));
    continue;
  } else if (ln.startsWith("@figure ")) {
    const [file, ...rest] = ln.slice(8).split("|");
    const { text } = stripLabel(rest.join("|"));
    const abs = path.join(process.env.FIG_CACHE || ROOT, file.trim());
    const { w, h } = pngSize(abs);
    const width = Math.round(Math.min(MAX_IMG_PX, w, (MAX_IMG_H_PX * w) / h));
    figN += 1;
    out().push(new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60, line: 240, lineRule: LineRuleType.AUTO },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(abs), transformation: { width, height: Math.round((width * h) / w) },
        altText: { title: `Figure ${figN}`, description: text, name: `figure${figN}` } })],
    }));
    out().push(captionPara("Figure", figN, text));
  } else if (ln.startsWith("@eq ")) {
    out().push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 },
      children: [new TextRun({ text: ln.slice(4), italics: true })] }));
  } else if (ln.startsWith("@references")) {
    i += 1;
    while (i < lines.length && lines[i].trim()) {
      out().push(new Paragraph({ style: "Reference", children: inline(lines[i].trim()) }));
      i += 1;
    }
    continue;
  } else if (ln.startsWith("- ")) {
    out().push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: inline(ln.slice(2)) }));
  } else {
    // paragraph: join following non-empty, non-directive lines
    let text = ln;
    while (i + 1 < lines.length && lines[i + 1].trim() && !/^(#|@|- )/.test(lines[i + 1])) { i += 1; text += " " + resolve(lines[i]); }
    out().push(new Paragraph({ children: inline(text) }));
  }
  i += 1;
}

// ------------------------------------------------------------------ cover page
const center = (text, opts = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: opts.after ?? 240, line: 276, lineRule: LineRuleType.AUTO },
  children: [new TextRun({ text, ...opts.run })] });
const cover = [
  center(COVER.institution, { run: { size: 32, bold: true }, after: 480 }),
  center(COVER.logo, { run: { size: 22, italics: true, color: "7F7F7F" }, after: 1400 }),
  center("Independent Project", { run: { size: 26, smallCaps: true }, after: 360 }),
  center(COVER.title, { run: { size: 34, bold: true }, after: 1400 }),
  center(`Student: ${COVER.student}`, { run: { size: 26 } }),
  center(`Academic Program: ${COVER.program}`, { run: { size: 26 } }),
  center(`Supervisor: ${COVER.supervisor}`, { run: { size: 26 } }),
  center(`Academic Year: ${COVER.year}`, { run: { size: 26 } }),
  center(`Date: ${COVER.date}`, { run: { size: 26 } }),
];

const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT] })] })] });
const page = (fmt) => ({
  size: { width: PAGE_W, height: PAGE_H },
  margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN, footer: 720 },
  pageNumbers: fmt ? { start: 1, formatType: fmt } : undefined,
});

const doc = new Document({
  creator: COVER.student,
  title: COVER.title,
  description: "Independent Project report — TamTam Digital School, 2026",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 360, lineRule: LineRuleType.AUTO, after: 120 }, alignment: AlignmentType.JUSTIFIED } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: "1F3864" },
        paragraph: { spacing: { before: 0, after: 240, line: 276, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.LEFT, keepNext: true, pageBreakBefore: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "1F3864" },
        paragraph: { spacing: { before: 300, after: 120, line: 276, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.LEFT, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, italics: true },
        paragraph: { spacing: { before: 200, after: 80, line: 276, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.LEFT, keepNext: true, outlineLevel: 2 } },
      { id: "Caption", name: "Caption", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 20, italics: false },
        paragraph: { spacing: { before: 60, after: 240, line: 240, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.CENTER } },
      { id: "TableText", name: "Table Text", basedOn: "Normal",
        run: { font: FONT, size: 20 }, paragraph: { spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.LEFT } },
      { id: "AfterTable", name: "After Table", basedOn: "Normal", paragraph: { spacing: { before: 0, after: 120, line: 240, lineRule: LineRuleType.AUTO } } },
      { id: "Reference", name: "Reference", basedOn: "Normal",
        paragraph: { indent: { left: 720, hanging: 720 }, alignment: AlignmentType.LEFT, spacing: { line: 360, lineRule: LineRuleType.AUTO, after: 120 } } },
      { id: "TocTitle", name: "TOC Title", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 32, bold: true, color: "1F3864" }, paragraph: { spacing: { after: 240 }, alignment: AlignmentType.LEFT } },
    ],
  },
  numbering: {
    config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }],
  },
  sections: [
    { properties: { page: page(null) }, children: cover },
    { properties: { page: page(NumberFormat.LOWER_ROMAN) }, footers: { default: footer }, children: sections.prelim },
    { properties: { page: page(NumberFormat.DECIMAL) }, footers: { default: footer }, children: sections.main },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`${OUT}: ${figN} figures, ${tabN} tables`);
});
