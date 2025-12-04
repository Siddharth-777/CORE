import { useEffect, useRef, useState } from "react";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [chatError, setChatError] = useState("");
  const [isProcessingStarted, setIsProcessingStarted] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  const [extractLoading, setExtractLoading] = useState(false);
  const [detectionPreview, setDetectionPreview] = useState("");
  const [extractionPreview, setExtractionPreview] = useState("");
  const [detectError, setDetectError] = useState("");
  const [extractError, setExtractError] = useState("");

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (isProcessingStarted && messages.length === 0) {
      setMessages([
        {
          id: 1,
          text: "Your PDF is parsed. Ask about coverage, exclusions, grace periods, or waiting periods — answers stay grounded in the document.",
          sender: "bot",
        },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProcessingStarted]);

  const validateFile = (file) => {
    if (file.type !== "application/pdf") {
      setUploadError("Please upload a PDF file only.");
      return false;
    }

    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError("File size exceeds 50MB limit. Please upload a smaller file.");
      return false;
    }

    return true;
  };

  const handleFileSelect = (file) => {
    setUploadError("");

    if (validateFile(file)) {
      setUploadedFile(file);
      setIsProcessingStarted(false);
      setSessionId(null);
      setMessages([]);
      setDetectionPreview("");
      setExtractionPreview("");
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleChooseFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleRemoveFile = () => {
    setUploadedFile(null);
    setUploadError("");
    setIsProcessingStarted(false);
    setMessages([]);
    setSessionId(null);
    setDetectionPreview("");
    setExtractionPreview("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleProcessFile = async () => {
    setUploadError("");
    setChatError("");

    if (!uploadedFile) {
      setUploadError("Please upload a PDF file before processing.");
      return;
    }

    try {
      setIsUploading(true);

      const formData = new FormData();
      formData.append("file", uploadedFile);

      const res = await fetch(`${BACKEND_URL}/hackrx/upload_file`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        let detail = `Upload failed with status ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setIsProcessingStarted(true);

      setMessages([
        {
          id: 1,
          text: "Your PDF has been uploaded successfully. I can assist you with questions about the structure extraction process, detected elements, or the output format. How may I assist you?",
          sender: "bot",
        },
      ]);
    } catch (err) {
      console.error(err);
      setUploadError(err.message || "Failed to process file.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    if (!sessionId) {
      setChatError("Please process a PDF first before asking questions.");
      return;
    }

    setChatError("");

    const userText = inputMessage.trim();

    const userMessage = {
      id: Date.now(),
      text: userText,
      sender: "user",
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");

    try {
      setIsAsking(true);

      const res = await fetch(`${BACKEND_URL}/hackrx/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          question: userText,
        }),
      });

      if (!res.ok) {
        let detail = `Backend error: ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data = await res.json();

      const botMessage = {
        id: Date.now() + 1,
        text: data.answer || "No answer returned.",
        sender: "bot",
        references: data.references || [],
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      setChatError(err.message || "Failed to get answer from backend.");
    } finally {
      setIsAsking(false);
    }
  };

  const requestBackendPreview = async (
    question,
    setter,
    errorSetter,
    loadingSetter
  ) => {
    if (!sessionId) {
      errorSetter("Upload and process a PDF first.");
      return;
    }

    errorSetter("");

    try {
      loadingSetter(true);
      const res = await fetch(`${BACKEND_URL}/hackrx/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question,
        }),
      });

      if (!res.ok) {
        let detail = `Backend error: ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data = await res.json();
      setter(data.answer || "No preview available yet.");
    } catch (err) {
      console.error(err);
      errorSetter(err.message || "Failed to fetch preview.");
    } finally {
      loadingSetter(false);
    }
  };

  const handleDetectPreview = () => {
    requestBackendPreview(
      "List the main headings and subheadings from this PDF with their nesting.",
      setDetectionPreview,
      setDetectError,
      setDetectLoading
    );
  };

  const handleExtractPreview = () => {
    requestBackendPreview(
      "Summarize the key content blocks under each detected section as bullet points.",
      setExtractionPreview,
      setExtractError,
      setExtractLoading
    );
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${Math.round((bytes / k ** i) * 100) / 100} ${sizes[i]}`;
  };

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" />
          PDF Structure Extractor
        </div>
        <nav className="topbar-actions">
          <button className="link-button" type="button">
            Docs
          </button>
          <button className="link-button" type="button">
            API
          </button>
          <button className="primary-button" disabled={!sessionId}>
            Export JSON
          </button>
        </nav>
      </header>

      <main className="content">
        <section className="hero">
          <div className="hero-text">
            <p className="eyebrow">Structured PDF workspace</p>
            <h1>Minimal surface, focused on the document</h1>
            <p className="lede">
              Upload a policy, contract, or report and review the outline, extracted highlights, and chat
              responses without distractions.
            </p>
            <div className="hero-actions">
              <button className="primary-button" type="button" onClick={handleChooseFileClick}>
                Start with a PDF
              </button>
              <button
                className="ghost-button"
                type="button"
                onClick={() => {
                  document.getElementById("upload")?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                Jump to upload
              </button>
            </div>
          </div>
          <div className="hero-quicklist">
            <div className="quick-item">
              <p className="quick-title">Outline aware</p>
              <p className="muted">Headings, subheadings, and tables stay grouped.</p>
            </div>
            <div className="quick-item">
              <p className="quick-title">JSON ready</p>
              <p className="muted">Export once you are happy with the preview.</p>
            </div>
            <div className="quick-item">
              <p className="quick-title">Assistant on-call</p>
              <p className="muted">Ask questions that stay grounded in your PDF.</p>
            </div>
          </div>
        </section>

        <section className="panel" id="upload">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 1</p>
              <h2>Upload and validate</h2>
              <p className="muted">Drop a single PDF up to 50MB. We keep the process quiet and clear.</p>
            </div>
            <span
              className={`status-chip ${uploadedFile ? "status-chip--ready" : "status-chip--idle"}`}
            >
              {uploadedFile ? "File ready" : "Waiting for file"}
            </span>
          </div>

          <div className="upload-area">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileInputChange}
              accept=".pdf,application/pdf"
              style={{ display: "none" }}
            />
            {!uploadedFile ? (
              <div
                className={`upload-zone ${isDragging ? "upload-zone--dragging" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={(e) => {
                  if (e.target.tagName !== "BUTTON") {
                    handleChooseFileClick();
                  }
                }}
              >
                <div className="upload-icon" />
                <div className="upload-copy">
                  <h3>Drop your PDF</h3>
                  <p className="muted">or click to choose from your computer</p>
                </div>
                <button
                  className="upload-button"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleChooseFileClick();
                  }}
                >
                  Browse files
                </button>
              </div>
            ) : (
              <div className="uploaded-file-card">
                <div className="file-info">
                  <div className="file-icon">
                    <div className="file-icon-pdf" />
                  </div>
                  <div className="file-details">
                    <h3 className="file-name">{uploadedFile.name}</h3>
                    <p className="file-size">{formatFileSize(uploadedFile.size)}</p>
                  </div>
                </div>
                <div className="file-actions">
                  <button
                    className="file-action-button file-action-button--primary"
                    onClick={handleProcessFile}
                    disabled={isUploading}
                  >
                    {isUploading ? "Processing…" : "Process"}
                  </button>
                  <button className="file-action-button" onClick={handleRemoveFile}>
                    Remove
                  </button>
                </div>
              </div>
            )}
            {uploadError && <div className="upload-error">{uploadError}</div>}
          </div>
        </section>

        <section className="panel minimal-grid">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2>Review the outline and content</h2>
              <p className="muted">
                Pull a quick outline, skim the extracted highlights, and move on to export when it looks right.
              </p>
            </div>
            <div className="progress-pill">
              <span className="progress-dot" />
              {sessionId ? "Document parsed" : "Waiting for processing"}
            </div>
          </div>

          <div className="grid two-col">
            <div className="preview-block">
              <div className="preview-header">
                <div>
                  <p className="muted">Detected outline</p>
                  <h3>Structure preview</h3>
                </div>
                <button
                  className="ghost-button"
                  onClick={handleDetectPreview}
                  disabled={!sessionId || detectLoading}
                >
                  {detectLoading ? "Fetching…" : "Fetch outline"}
                </button>
              </div>
              <div className="structure-box">
                {detectionPreview ? (
                  detectionPreview.split("\n").map((line, idx) => (
                    <div key={idx} className="structure-row">
                      {line}
                    </div>
                  ))
                ) : (
                  <p className="placeholder-text">
                    No preview yet. Process and fetch to see headings and subheadings.
                  </p>
                )}
              </div>
              {detectError && <div className="upload-error">{detectError}</div>}
            </div>

            <div className="preview-block">
              <div className="preview-header">
                <div>
                  <p className="muted">Extracted notes</p>
                  <h3>Content snapshot</h3>
                </div>
                <button
                  className="ghost-button"
                  onClick={handleExtractPreview}
                  disabled={!sessionId || extractLoading}
                >
                  {extractLoading ? "Fetching…" : "Fetch summary"}
                </button>
              </div>
              <div className="structure-box">
                {extractionPreview ? (
                  extractionPreview.split("\n").map((line, idx) => (
                    <div key={idx} className="structure-row">
                      {line}
                    </div>
                  ))
                ) : (
                  <p className="placeholder-text">
                    Grab a summary to see how content is grouped before exporting.
                  </p>
                )}
              </div>
              {extractError && <div className="upload-error">{extractError}</div>}
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 3</p>
              <h2>Ask the assistant</h2>
              <p className="muted">Clarify sections, check exclusions, or validate the hierarchy.</p>
            </div>
            <span className="status-chip status-chip--soft">
              {sessionId ? "Ready" : "Upload to enable"}
            </span>
          </div>

          <div className="chat-section">
            {!sessionId ? (
              <div className="chat-placeholder">
                <p className="quick-title">Waiting for a PDF</p>
                <p className="muted">Process a document to unlock grounded answers.</p>
              </div>
            ) : (
              <div className="chat-window">
                <div className="chat-messages">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`chat-message chat-message--${msg.sender}`}>
                      <div className="chat-bubble">
                        <p>{msg.text}</p>
                        {msg.references?.length > 0 && (
                          <div className="references">
                            <p className="references-title">References</p>
                            <ul>
                              {msg.references.map((ref, idx) => (
                                <li key={idx}>
                                  <a href={ref.url} target="_blank" rel="noreferrer">
                                    {ref.text}
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {messages.length === 0 && (
                    <div className="placeholder-text">
                      Ask about the detected outline, extraction confidence, or specific sections.
                    </div>
                  )}
                </div>

                {chatError && <div className="upload-error">{chatError}</div>}
              </div>
            )}

            <div className="chat-input-container">
              <input
                type="text"
                className="chat-input"
                placeholder={
                  sessionId
                    ? "Ask about document structure, extraction process, or output format..."
                    : "Process a PDF first to activate the assistant."
                }
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === "Enter" && inputMessage.trim()) {
                    handleSendMessage();
                  }
                }}
              />
              <button
                className="chat-send-button"
                onClick={handleSendMessage}
                disabled={!inputMessage.trim() || !sessionId || isAsking}
              >
                {isAsking ? "Thinking…" : "Send"}
              </button>
            </div>
          </div>
        </section>

        <section className="panel principles">
          <div className="principles-grid">
            <div className="principle">
              <p className="quick-title">Stay minimal</p>
              <p className="muted">Simple surfaces with clear actions keep focus on the file.</p>
            </div>
            <div className="principle">
              <p className="quick-title">Keep hierarchy intact</p>
              <p className="muted">Headings, tables, and paragraphs stay linked to their sections.</p>
            </div>
            <div className="principle">
              <p className="quick-title">Export with confidence</p>
              <p className="muted">Review previews before sending JSON downstream.</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
