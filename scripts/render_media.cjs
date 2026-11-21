// Media for the README and for sharing, rendered with Playwright (Chromium).
//
//   node scripts/render_media.cjs dashboard <site-dir> <out.png> <width>   dashboard screenshot, 2x
//   node scripts/render_media.cjs social <fonts-dir> <stores> <products> <out.png>   1280 x 640 preview
//   node scripts/render_media.cjs frames <square.svg> <frames-dir>         30 fps frames of the 8 s loop
//
// Frames are encoded by ffmpeg (scripts/make_media.sh).
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [cmd, ...args] = process.argv.slice(2);

async function dashboard(siteDir, out, width) {
  const w = Number(width || 1280);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 2 })).newPage();
  await page.goto("file://" + path.resolve(siteDir, "index.html"));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: w, height: w > 600 ? 1000 : 1600 } });
  await browser.close();
}

async function social(fontsDir, stores, products, out) {
  const font = (f) => "data:font/woff2;base64," + fs.readFileSync(path.join(fontsDir, f)).toString("base64");
  const html = `<!doctype html><html><head><style>
    @font-face{font-family:PJ;font-weight:400;src:url(${font("plus-jakarta-sans-400.woff2")})}
    @font-face{font-family:PJ;font-weight:700;src:url(${font("plus-jakarta-sans-700.woff2")})}
    @font-face{font-family:PJ;font-weight:800;src:url(${font("plus-jakarta-sans-800.woff2")})}
    body{margin:0;width:1280px;height:640px;background:#FFFFFF;color:#0B1416;font-family:PJ;position:relative}
    .wrap{padding:80px 96px;height:100%;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;gap:26px}
    .kicker{font-weight:700;font-size:30px;color:#0B7468}
    h1{font-size:84px;line-height:1.02;margin:0;font-weight:800;letter-spacing:-.02em}
    p{font-size:36px;color:#3D4B49;margin:0;max-width:1000px;line-height:1.3}
    .foot{margin-top:18px;font-size:28px;color:#5F716E;display:flex;gap:22px}
    .bar{position:absolute;left:96px;top:60px;width:120px;height:8px;border-radius:4px;background:#0B7468}
    .side{position:absolute;right:0;top:0;width:28px;height:640px;background:#E3F3F0}
  </style></head><body><div class="bar"></div><div class="side"></div><div class="wrap">
    <div class="kicker">${stores} US stores · ${products} products · every day</div>
    <h1>Cross-store price comparison</h1>
    <p>The same products at different stores, matched by barcode: lowest price, price gap and stock.</p>
    <div class="foot"><span>SteadyData</span><span>·</span><span>steadydata.co</span></div>
  </div></body></html>`;
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 })).newPage();
  await page.setContent(html);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: out });
  await browser.close();
}

async function frames(svgFile, dir) {
  fs.mkdirSync(dir, { recursive: true });
  const svg = fs.readFileSync(svgFile, "utf8");
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1080, height: 1080 }, deviceScaleFactor: 1 })).newPage();
  await page.setContent(`<!doctype html><body style="margin:0;background:#FFFFFF">${svg}</body>`);
  await page.evaluate(async () => {
    await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
    await document.fonts.ready;
  });
  const fps = 30, loop = 8, hold = 2;
  let n = 0;
  for (let i = 0; i < (loop + hold) * fps; i++) {
    const t = Math.min(i / fps, loop - 0.001) * 1000;
    await page.evaluate((ms) => document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; }), t);
    await page.screenshot({ path: path.join(dir, `f${String(n++).padStart(4, "0")}.png`), clip: { x: 0, y: 0, width: 1080, height: 1080 } });
  }
  await browser.close();
  console.log(`${n} frames`);
}

(async () => {
  if (cmd === "dashboard") await dashboard(...args);
  else if (cmd === "social") await social(...args);
  else if (cmd === "frames") await frames(...args);
  else { console.error("usage: dashboard|social|frames"); process.exit(2); }
})();
