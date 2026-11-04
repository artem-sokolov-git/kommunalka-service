// Sends the bill. Where the browser can share files, the button opens the system share sheet with
// the PDF; elsewhere the menu (Telegram, mail, download) stays as the page renders it.
const menu = document.querySelector("[data-send-bill]");
const link = menu?.querySelector("[data-bill-pdf]");

async function fetchPdf() {
  const response = await fetch(link.href);
  if (!response.ok) throw new Error(`PDF request failed: ${response.status}`);
  return new File([await response.blob()], link.getAttribute("download"), {
    type: "application/pdf",
  });
}

const probe = new File([""], "probe.pdf", { type: "application/pdf" });

if (menu && navigator.canShare?.({ files: [probe] })) {
  menu.querySelector("summary").addEventListener("click", async (event) => {
    event.preventDefault();
    menu.setAttribute("aria-busy", "true");
    try {
      // Files only: with a title or text some share targets (Telegram on macOS) drop the file.
      await navigator.share({ files: [await fetchPdf()] });
    } catch (error) {
      if (error.name !== "AbortError") throw error;
    } finally {
      menu.removeAttribute("aria-busy");
    }
  });
}
