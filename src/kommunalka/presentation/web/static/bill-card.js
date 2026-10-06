// Draws a bill as a picture and hands it to the system share sheet (Telegram and others),
// or downloads it where sharing files isn't available.
const button = document.querySelector("[data-share-bill]");
const data = JSON.parse(document.getElementById("bill-card")?.textContent ?? "null");

const WIDTH = 1080;
const MARGIN = 48;
const PADDING = 64;
const LINE = 132;
const FONT = "Manrope, system-ui, sans-serif";
const COLORS = {
  bg: "#f4f3ef",
  surface: "#ffffff",
  text: "#16191d",
  muted: "#5f6670",
  line: "#e3e1da",
  accent: "#1d5fb4",
  down: ["#e3f1e8", "#23603c"],
  up: ["#fff4e5", "#9a4d00"],
  same: ["#f4f3ef", "#5f6670"],
};
const ICONS = {
  gas: { bg: "#fcebd8", ink: "#9a4d00", paths: ["M12 3c1 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-4 2.5-5 0 2 1 3 2.5 3 0-3-1-5 0-8z"] },
  power: { bg: "#e8eff8", ink: "#1d5fb4", paths: ["M13 2 4 14h7l-1 8 9-12h-7l1-8z"] },
  fixed: { bg: "#ecedef", ink: "#4a515a", paths: ["M3 8h11a4 4 0 0 1 4 4v9", "M3 14h7a2 2 0 0 1 2 2v5"] },
};
const HOUSE = ["M3 11 12 4l9 7", "M5 10v10h14V10"];

function font(ctx, weight, size) {
  ctx.font = `${weight} ${size}px ${FONT}`;
}

function fit(ctx, text, width) {
  if (ctx.measureText(text).width <= width) return text;
  while (text && ctx.measureText(`${text}…`).width > width) text = text.slice(0, -1);
  return `${text}…`;
}

function icon(ctx, paths, x, y, size, color) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(size / 24, size / 24);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const path of paths) ctx.stroke(new Path2D(path));
  ctx.restore();
}

function box(ctx, x, y, width, height, radius, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(x, y, width, height, radius);
  ctx.fill();
}

function detail(line) {
  if (!line.quantity) return "сумма за месяц";
  const used = `${line.quantity} × ${line.price}`;
  return line.readings ? `${line.readings} · ${used}` : used;
}

function draw(canvas) {
  const height = MARGIN * 2 + PADDING * 2 + 64 + 56 + 54 + 130 + (data.change ? 92 : 24) + 8
    + data.lines.length * LINE;
  canvas.width = WIDTH;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const left = MARGIN + PADDING;
  const right = WIDTH - MARGIN - PADDING;
  ctx.textBaseline = "alphabetic";

  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, WIDTH, height);
  box(ctx, MARGIN, MARGIN, WIDTH - MARGIN * 2, height - MARGIN * 2, 40, COLORS.surface);

  let y = MARGIN + PADDING;
  box(ctx, left, y, 64, 64, 18, COLORS.accent);
  icon(ctx, HOUSE, left + 14, y + 14, 36, "#ffffff");
  font(ctx, 800, 36);
  ctx.fillStyle = COLORS.text;
  ctx.fillText("Коммуналка", left + 88, y + 45);
  font(ctx, 600, 30);
  ctx.fillStyle = COLORS.muted;
  ctx.textAlign = "right";
  ctx.fillText(fit(ctx, data.household, 380), right, y + 44);
  ctx.textAlign = "left";

  y += 64 + 56;
  font(ctx, 600, 34);
  ctx.fillText(`Счёт за ${data.month} ${data.year}`, left, y + 34);

  y += 54;
  font(ctx, 800, 120);
  ctx.fillStyle = COLORS.text;
  ctx.fillText(data.total, left, y + 110);
  const totalWidth = ctx.measureText(data.total).width;
  font(ctx, 600, 52);
  ctx.fillStyle = COLORS.muted;
  ctx.fillText("грн", left + totalWidth + 20, y + 110);

  y += 130;
  if (data.change) {
    const [bg, ink] = COLORS[data.change.direction];
    font(ctx, 600, 30);
    const width = ctx.measureText(data.change.text).width + 44;
    box(ctx, left, y, width, 56, 28, bg);
    ctx.fillStyle = ink;
    ctx.fillText(data.change.text, left + 22, y + 38);
    y += 92;
  } else {
    y += 24;
  }

  ctx.fillStyle = COLORS.line;
  ctx.fillRect(left, y, right - left, 2);
  y += 8;

  data.lines.forEach((line, index) => {
    const kind = ICONS[line.kind] ?? ICONS.fixed;
    box(ctx, left, y + 26, 80, 80, 22, kind.bg);
    icon(ctx, kind.paths, left + 19, y + 45, 42, kind.ink);

    font(ctx, 700, 38);
    ctx.fillStyle = COLORS.text;
    ctx.textAlign = "right";
    ctx.fillText(line.amount, right, y + 78);
    const amountWidth = ctx.measureText(line.amount).width;
    ctx.textAlign = "left";
    const textWidth = right - left - 104 - amountWidth - 32;

    font(ctx, 700, 36);
    ctx.fillText(fit(ctx, line.name, textWidth), left + 104, y + 62);
    font(ctx, 500, 26);
    ctx.fillStyle = COLORS.muted;
    ctx.fillText(fit(ctx, detail(line), textWidth), left + 104, y + 102);

    if (index < data.lines.length - 1) {
      ctx.fillStyle = COLORS.line;
      ctx.fillRect(left, y + LINE - 1, right - left, 2);
    }
    y += LINE;
  });
}

async function render() {
  await Promise.all(
    [500, 600, 700, 800].map((weight) => document.fonts.load(`${weight} 36px Manrope`)),
  ).catch(() => {});
  const canvas = document.createElement("canvas");
  draw(canvas);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

function download(blob) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = data.file;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

const probe = new File([""], "probe.png", { type: "image/png" });
const canShareFiles = Boolean(navigator.canShare?.({ files: [probe] }));

if (button && data) {
  if (!canShareFiles) button.querySelector("span").textContent = "Скачать картинку";
  button.hidden = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const blob = await render();
      const file = new File([blob], data.file, { type: "image/png" });
      if (canShareFiles) {
        // Files only: with a title or text some share targets (Telegram on macOS) drop the file.
        await navigator.share({ files: [file] });
      } else {
        download(blob);
      }
    } catch (error) {
      if (error.name !== "AbortError") throw error;
    } finally {
      button.disabled = false;
    }
  });
}
