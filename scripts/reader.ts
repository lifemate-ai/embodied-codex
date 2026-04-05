import { Readability } from "@mozilla/readability";
import { parseHTML } from "linkedom";

const CHARS_PER_PAGE = 2000;

function usage() {
  console.log(`Usage: bun run scripts/reader.ts <url> [options]

Options:
  --page <n>   Show only page N (1-indexed)
  --info       Show title and page count only`);
  process.exit(1);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) usage();

  let url = "";
  let page: number | null = null;
  let infoOnly = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--page") {
      page = parseInt(args[++i], 10);
    } else if (args[i] === "--info") {
      infoOnly = true;
    } else if (!args[i].startsWith("--")) {
      url = args[i];
    }
  }

  if (!url) usage();

  let html: string;
  const isLocalFile = !url.startsWith("http://") && !url.startsWith("https://");

  if (isLocalFile) {
    const path = await import("node:path");
    const resolved = path.resolve(url);
    const file = Bun.file(resolved);
    if (!(await file.exists())) {
      console.error(`File not found: ${resolved}`);
      process.exit(1);
    }
    html = await file.text();
  } else {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; ShiroeReader/1.0)",
      },
    });

    if (!res.ok) {
      console.error(`Fetch failed: ${res.status} ${res.statusText}`);
      process.exit(1);
    }

    html = await res.text();
  }
  const { document } = parseHTML(html);

  const reader = new Readability(document as any);
  const article = reader.parse();

  if (!article || !article.textContent) {
    console.error("Readability could not extract content from this page.");
    process.exit(1);
  }

  const title = article.title || "(no title)";
  const text = article.textContent.trim();
  const totalPages = Math.ceil(text.length / CHARS_PER_PAGE);

  if (infoOnly) {
    console.log(`Title: ${title}`);
    console.log(`Length: ${text.length} chars`);
    console.log(`Pages: ${totalPages} (${CHARS_PER_PAGE} chars/page)`);
    return;
  }

  console.log(`# ${title}\n`);

  if (page !== null) {
    if (page < 1 || page > totalPages) {
      console.error(`Page ${page} out of range (1-${totalPages})`);
      process.exit(1);
    }
    const start = (page - 1) * CHARS_PER_PAGE;
    const end = start + CHARS_PER_PAGE;
    const slice = text.slice(start, end);
    console.log(slice);
    console.log(`\n--- Page ${page}/${totalPages} ---`);
  } else {
    console.log(text);
    console.log(`\n--- ${text.length} chars, ${totalPages} pages ---`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
