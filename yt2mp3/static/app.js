(() => {
  const urlInput = document.getElementById("url");
  const videoInfo = document.getElementById("video-info");
  const thumbnail = document.getElementById("thumbnail");
  const title = document.getElementById("title");
  const uploader = document.getElementById("uploader");
  const duration = document.getElementById("duration");
  const endInput = document.getElementById("end");
  const downloadBtn = document.getElementById("download-btn");
  const status = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const progressBar = document.getElementById("progress-bar");
  const errorBox = document.getElementById("error");

  let infoDebounce = null;
  let lastFetchedUrl = null;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function setStatus(text) {
    status.hidden = false;
    statusText.textContent = text;
  }

  function hideStatus() {
    status.hidden = true;
  }

  function setProgressInProgress() {
    progressBar.classList.add("indeterminate");
    progressBar.classList.remove("complete");
  }

  function setProgressComplete() {
    progressBar.classList.remove("indeterminate");
    progressBar.classList.add("complete");
  }

  async function fetchInfo() {
    const url = urlInput.value.trim();
    if (!url || url === lastFetchedUrl) return;

    clearError();
    videoInfo.hidden = true;
    setProgressInProgress();
    setStatus("Fetching video information...");

    try {
      const res = await fetch("/api/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (!res.ok) {
        hideStatus();
        showError(data.error || "Unable to fetch video information.");
        return;
      }

      lastFetchedUrl = url;
      title.textContent = data.title;
      uploader.textContent = data.uploader;
      duration.textContent = data.duration_formatted ? `Duration: ${data.duration_formatted}` : "";
      endInput.placeholder = data.duration_formatted || "End of video";

      if (data.thumbnail_url) {
        thumbnail.src = data.thumbnail_url;
        thumbnail.hidden = false;
      } else {
        thumbnail.hidden = true;
      }

      videoInfo.hidden = false;
      hideStatus();
    } catch (err) {
      hideStatus();
      showError("Unable to reach the server. Please try again.");
    }
  }

  urlInput.addEventListener("input", () => {
    clearError();
    if (infoDebounce) clearTimeout(infoDebounce);
    infoDebounce = setTimeout(fetchInfo, 600);
  });

  downloadBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showError("Please enter a YouTube URL.");
      return;
    }

    clearError();
    downloadBtn.disabled = true;

    const payload = {
      url,
      format: document.getElementById("format").value,
      quality: document.getElementById("quality").value,
      bitrate: document.getElementById("bitrate").value,
      start: document.getElementById("start").value.trim() || null,
      end: endInput.value.trim() || null,
    };

    const isClip = Boolean(payload.start || payload.end);
    const baseMessage = isClip
      ? "Downloading requested clip and converting"
      : "Downloading full audio and converting (longer videos take longer)";

    const startedAt = Date.now();
    setProgressInProgress();
    setStatus(`${baseMessage}...`);
    const tick = setInterval(() => {
      const elapsed = Math.round((Date.now() - startedAt) / 1000);
      setStatus(`${baseMessage}... (${elapsed}s)`);
    }, 1000);

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      clearInterval(tick);

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        hideStatus();
        showError(data.error || "Unable to download this video.");
        return;
      }

      setStatus("Preparing file...");
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `audio.${payload.format}`;

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);

      setProgressComplete();
      setStatus("Completed");
    } catch (err) {
      clearInterval(tick);
      hideStatus();
      showError("Unable to download this video. The video may be unavailable or restricted.");
    } finally {
      downloadBtn.disabled = false;
    }
  });
})();
