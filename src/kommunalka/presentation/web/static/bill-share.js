// Hands the bill PDF to the system share sheet (Telegram and others) where sharing files is
// available; otherwise the link downloads the PDF as it is.
const link = document.querySelector("[data-share-bill]");

async function fetchPdf() {
  const response = await fetch(link.href);
  if (!response.ok) throw new Error(`PDF request failed: ${response.status}`);
  return new File([await response.blob()], link.getAttribute("download"), {
    type: "application/pdf",
  });
}

const probe = new File([""], "probe.pdf", { type: "application/pdf" });

if (link && navigator.canShare?.({ files: [probe] })) {
  link.querySelector("span").textContent = "Поделиться";
  link.addEventListener("click", async (event) => {
    event.preventDefault();
    link.setAttribute("aria-disabled", "true");
    try {
      // Files only: with a title or text some share targets (Telegram on macOS) drop the file.
      await navigator.share({ files: [await fetchPdf()] });
    } catch (error) {
      if (error.name !== "AbortError") throw error;
    } finally {
      link.removeAttribute("aria-disabled");
    }
  });
}
