const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const dropzone = document.getElementById("dropzone");
const fileName = document.getElementById("fileName");
const message = document.getElementById("message");

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const resumeBtn = document.getElementById("resumeBtn");
const zipBtn = document.getElementById("zipBtn");

const tableBody = document.getElementById("tableBody");
const jobStatus = document.getElementById("jobStatus");

let jobId = null;
let pollTimer = null;

browseBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadExcel(fileInput.files[0]);
});

["dragenter", "dragover"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
});

["dragleave", "drop"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
    });
});

dropzone.addEventListener("drop", e => {
    const file = e.dataTransfer.files[0];
    if (file) uploadExcel(file);
});

async function uploadExcel(file) {
    if (!/\.(xlsx|xls)$/i.test(file.name)) {
        showMessage("Please select an .xlsx or .xls file.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    fileName.textContent = `Selected: ${file.name}`;
    showMessage("Reading Excel and preparing PDF list...");

    try {
        const response = await fetch("/api/upload/", {
            method: "POST",
            body: formData
        });

        const data = await response.json();
        if (!data.ok) throw new Error(data.error);

        jobId = data.job_id;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        resumeBtn.disabled = true;
        zipBtn.disabled = true;

        showMessage(`${data.total} PDF URLs found. Click Start Download.`);
        await pollStatus();
    } catch (error) {
        showMessage(error.message, true);
    }
}

startBtn.addEventListener("click", async () => {
    await post(`/api/job/${jobId}/start/`);
});

stopBtn.addEventListener("click", async () => {
    await post(`/api/job/${jobId}/stop/`);
});

resumeBtn.addEventListener("click", async () => {
    await post(`/api/job/${jobId}/resume/`);
});

zipBtn.addEventListener("click", () => {
    if (jobId) window.location.href = `/api/job/${jobId}/zip/`;
});

async function post(url) {
    try {
        const response = await fetch(url, { method: "POST" });
        const data = await response.json();
        if (!data.ok) throw new Error(data.error);
        await pollStatus();
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function pollStatus() {
    if (!jobId) return;

    try {
        const response = await fetch(`/api/job/${jobId}/status/`);
        const data = await response.json();

        if (!data.ok) throw new Error(data.error);

        updateStats(data);
        renderTable(data.pdfs);
        jobStatus.textContent = data.status.toUpperCase();

        startBtn.disabled = !["ready"].includes(data.status);
        stopBtn.disabled = data.status !== "running";
        resumeBtn.disabled = !["stopped", "completed"].includes(data.status) && data.failed === 0;
        zipBtn.disabled = !data.zip_ready;

        if (data.status === "completed") {
            showMessage("All downloads completed successfully/with reported failures. ZIP is ready.");
        } else if (data.status === "stopped") {
            showMessage("Download stopped. Click Resume to continue from completed files.");
        }

        clearTimeout(pollTimer);
        if (["running", "ready"].includes(data.status)) {
            pollTimer = setTimeout(pollStatus, 700);
        }
    } catch (error) {
        showMessage(error.message, true);
    }
}

function updateStats(data) {
    document.getElementById("total").textContent = data.total;
    document.getElementById("success").textContent = data.success;
    document.getElementById("failed").textContent = data.failed;
    document.getElementById("downloading").textContent = data.downloading;
    document.getElementById("pending").textContent = data.pending;
}

function renderTable(pdfs) {
    if (!pdfs.length) {
        tableBody.innerHTML = `<tr><td colspan="6" class="empty">No PDFs found.</td></tr>`;
        return;
    }

    tableBody.innerHTML = pdfs.map(pdf => {
        const status = pdf.status || "pending";
        const label = status.charAt(0).toUpperCase() + status.slice(1);
        const action = status === "success"
            ? `<button class="action-btn" onclick="downloadPdf(${pdf.id})">Download</button>`
            : "—";

        return `
            <tr>
                <td>${pdf.id}</td>
                <td title="${escapeHtml(pdf.url)}">${escapeHtml(pdf.filename)}</td>
                <td class="status status-${status}">${label}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" style="width:${pdf.progress || 0}%"></div>
                    </div>
                    <small>${pdf.progress || 0}%</small>
                </td>
                <td>${escapeHtml(pdf.error || "")}</td>
                <td>${action}</td>
            </tr>
        `;
    }).join("");
}

function downloadPdf(id) {
    window.location.href = `/api/job/${jobId}/pdf/${id}/`;
}

function showMessage(text, error = false) {
    message.textContent = text;
    message.classList.remove("hidden");
    message.style.background = error ? "#fef2f2" : "#eff6ff";
    message.style.color = error ? "#b91c1c" : "#1d4ed8";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
