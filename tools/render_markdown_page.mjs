#!/usr/bin/env node

/**
 * Render a repository Markdown document into a complete, accessible Locus
 * documentation page. The source Markdown remains the authoring format; this
 * tool is used only while staging the static site.
 */
import fs from 'node:fs';
import path from 'node:path';
import MarkdownIt from 'markdown-it';
import anchor from 'markdown-it-anchor';

const posix = path.posix;

function usage() {
  console.error('Usage: render_markdown_page.mjs <source.md> <output.html> <source-base> <output-base>');
  process.exit(2);
}

const [, , sourcePath, outputPath, sourceBase, outputBase] = process.argv;
if (!sourcePath || !outputPath || !sourceBase || !outputBase) usage();

function escapeHtml(value) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function slugify(value) {
  return String(value).trim().toLowerCase().replace(/[\s]+/g, '-').replace(/[^\w\-]/g, '');
}

function outputHref(href) {
  if (!href || href.startsWith('#') || href.startsWith('/') || /^[a-z][a-z0-9+.-]*:/i.test(href)) {
    return href;
  }
  const match = href.match(/^([^?#]*)(.*)$/);
  const target = posix.normalize(posix.join(sourceBase, match[1]));
  return `${posix.relative(outputBase, target) || '.'}${match[2]}`;
}

const markdown = new MarkdownIt({html: false, linkify: true, typographer: true})
  .use(anchor, {slugify});

const defaultLinkOpen = markdown.renderer.rules.link_open ||
  ((tokens, index, options, environment, self) => self.renderToken(tokens, index, options));
markdown.renderer.rules.link_open = (tokens, index, options, environment, self) => {
  const hrefIndex = tokens[index].attrIndex('href');
  if (hrefIndex >= 0) tokens[index].attrs[hrefIndex][1] = outputHref(tokens[index].attrs[hrefIndex][1]);
  return defaultLinkOpen(tokens, index, options, environment, self);
};

const defaultTableOpen = markdown.renderer.rules.table_open ||
  ((tokens, index, options, environment, self) => self.renderToken(tokens, index, options));
const defaultTableClose = markdown.renderer.rules.table_close ||
  ((tokens, index, options, environment, self) => self.renderToken(tokens, index, options));
markdown.renderer.rules.table_open = (tokens, index, options, environment, self) =>
  '<div class="reference-table-scroll" role="region" aria-label="Format table" tabindex="0">' +
  defaultTableOpen(tokens, index, options, environment, self);
markdown.renderer.rules.table_close = (tokens, index, options, environment, self) =>
  defaultTableClose(tokens, index, options, environment, self) + '</div>\n';

const source = fs.readFileSync(sourcePath, 'utf8');
const tokens = markdown.parse(source, {});
const toc = [];
for (let index = 0; index < tokens.length; index += 1) {
  const token = tokens[index];
  if (token.type !== 'heading_open' || !['h2', 'h3'].includes(token.tag)) continue;
  const inline = tokens[index + 1];
  toc.push({level: token.tag.slice(1), id: token.attrGet('id'), label: (inline.children || []).filter(child => ['text', 'code_inline'].includes(child.type)).map(child => child.content).join('')});
}

const tocItems = toc.map(({level, id, label}) =>
  `<li class="reference-toc-level-${level}"><a href="#${escapeHtml(id)}">${escapeHtml(label)}</a></li>`).join('');
const tocHtml = `<details class="reference-toc" open><summary>On this page</summary><ol>${tocItems}</ol></details>`;
const completeGuide = path.basename(sourcePath) === 'locusplace-format.md';
const pageTitle = completeGuide ? 'Complete Locus Package v2 authoring' : 'Public Locus Package v2 and compatibility ZIP formats';
const sourceName = path.basename(sourcePath);
const route = outputBase.replace(/^\/+|\/+$/g, '');
const canonical = `https://enterlocus.com/${route}/`;
const toolsHtml = `<div class="reference-tools"><a class="reference-download" href="../${escapeHtml(sourceName)}" download>Download Markdown</a></div>`;
const article = markdown.render(source).replace(/<h1([^>]*)>([\s\S]*?)<\/h1>/, `<p class="kicker">Technical reference</p><h1$1>$2</h1>${toolsHtml}${tocHtml}`);

const document = `<!doctype html>
<!-- Generated from reference/${sourceName} by tools/render_markdown_page.mjs. Do not edit directly. -->
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0d141a">
  <title>${escapeHtml(pageTitle)} — Locus</title>
  <meta name="description" content="The complete Locus Package v2 and legacy compatibility ZIP authoring reference.">
  <meta property="og:title" content="${escapeHtml(pageTitle)}"><meta property="og:description" content="Exact Package v2 structure, capabilities, fields, limits, and compatibility formats."><meta property="og:type" content="website"><meta property="og:url" content="${canonical}"><meta property="og:image" content="https://enterlocus.com/assets/og.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://enterlocus.com/assets/og.png">
  <link rel="canonical" href="${canonical}"><link rel="icon" type="image/png" href="../../assets/favicon.png"><link rel="apple-touch-icon" href="../../assets/apple-touch-icon.png">
  <link rel="stylesheet" href="../../assets/site.css"><link rel="stylesheet" href="../../assets/docs.css"><link rel="stylesheet" href="../../assets/reference.css">
  <link rel="stylesheet" href="/assets/search.css"><script type="module" src="/assets/search.js"></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header"><a class="brand" href="../../" aria-label="Locus home"><span class="brand-mark" aria-hidden="true"><span></span></span><span>Locus</span></a><nav aria-label="Primary navigation"><a href="../../whats-new/">What’s New</a><a href="../../gallery/">Gallery</a><a aria-current="page" href="../../tutorials/">Tutorials</a><a href="../../faq/">FAQ</a><a href="../../support/">Support</a><a href="https://www.reddit.com/r/EnterLocus/">Community</a><button class="search-trigger" type="button" hidden aria-haspopup="dialog"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>Search</button></nav></header>
  <main data-pagefind-body id="main" class="page-main reference-page"><article class="reference-content">${article}</article></main>
  <footer><div><span class="brand-footer">Locus</span><span>Locus for Apple Vision Pro.</span></div><nav aria-label="Footer navigation"><a href="../../whats-new/">What’s New</a><a href="../../gallery/">Gallery</a><a href="../../tutorials/">Tutorials</a><a href="../../faq/">FAQ</a><a href="../../support/">Support</a><a href="../../privacy/">Privacy</a><a href="https://www.reddit.com/r/EnterLocus/">Community</a><a href="https://github.com/EnterLocus/locus-support/issues/new?template=bug.yml">Report a Bug</a></nav></footer>
</body>
</html>`;

fs.mkdirSync(path.dirname(outputPath), {recursive: true});
fs.writeFileSync(outputPath, document);
