import { useEffect, useRef, useState } from "react";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function App() {
  const [activeTab, setActiveTab] = useState("upload");
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
      setActiveTab("detect");

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
    <div className="app-shell">
      <header className="shell-header">
        <div className="shell-header-inner">
          <div className="shell-logo">
            <span className="logo-icon" />
            PDF Structure Extractor
          </div>
          <nav className="shell-header-actions">
            <button className="ghost-button">Documentation</button>
            <button className="ghost-button">API</button>
            <button className="primary-button" disabled={!sessionId}>
              Export JSON
            </button>
          </nav>
        </div>
      </header>

      <div className="shell-body">
        <aside className="shell-sidebar">
          <div className="sidebar-section">
            <p className="sidebar-label">WORKFLOW</p>
            <button
              className={`sidebar-item ${
                activeTab === "upload" ? "sidebar-item--active" : ""
              }`}
              onClick={() => setActiveTab("upload")}
            >
              <span className="step-badge">1</span>
              <span>Upload PDF</span>
            </button>
            <button
              className={`sidebar-item ${
                activeTab === "detect" ? "sidebar-item--active" : ""
              }`}
              onClick={() => setActiveTab("detect")}
              disabled={!sessionId}
            >
              <span className="step-badge">2</span>
              <span>Detect Structure</span>
            </button>
            <button
              className={`sidebar-item ${
                activeTab === "extract" ? "sidebar-item--active" : ""
              }`}
              onClick={() => setActiveTab("extract")}
              disabled={!sessionId}
            >
              <span className="step-badge">3</span>
              <span>Extract Content</span>
            </button>
            <button
              className={`sidebar-item ${
                activeTab === "chatbot" ? "sidebar-item--active" : ""
              }`}
              onClick={() => setActiveTab("chatbot")}
            >
              <span className="sidebar-icon sidebar-icon--chat" />
              <span>Chatbot</span>
            </button>
          </div>
          <div className="sidebar-section">
            <p className="sidebar-label">SYSTEM</p>
            <button
              className={`sidebar-item ${
                activeTab === "settings" ? "sidebar-item--active" : ""
              }`}
              onClick={() => setActiveTab("settings")}
            >
              <span className="sidebar-icon sidebar-icon--settings" />
              <span>Settings</span>
            </button>
            <button className="sidebar-item" disabled>
              <span className="sidebar-icon sidebar-icon--history" />
              <span>History</span>
            </button>
          </div>
        </aside>

        <main className="shell-main">
          {activeTab === "upload" && (
            <>
              <section className="shell-hero">
                <div>
                  <div className="eyebrow-container">
                    <span className="eyebrow">Step 1: Upload</span>
                    <span
                      className={`status-badge ${
                        uploadedFile ? "status-badge--success" : "status-badge--ready"
                      }`}
                    >
                      {uploadedFile ? "File Ready" : "Ready"}
                    </span>
                  </div>
                  <h1>Upload your PDF document</h1>
                  <p className="hero-copy">
                    Companies have lots of PDFs that are messy and unstructured. These files
                    have headings, subheadings, tables, and different formats. Upload your PDF
                    to begin the extraction process.
                  </p>
                </div>
              </section>
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
                    <h3>Drag & drop your PDF here</h3>
                    <p>or click to browse files</p>
                    <button
                      className="upload-button"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleChooseFileClick();
                      }}
                    >
                      Choose File
                    </button>
                    <p className="upload-hint">Supports PDF files up to 50MB</p>
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
                        {isUploading ? "Processing…" : "Process File"}
                      </button>
                      <button className="file-action-button" onClick={handleRemoveFile}>
                        Remove
                      </button>
                    </div>
                  </div>
                )}
                {uploadError && <div className="upload-error">{uploadError}</div>}
              </div>
            </>
          )}

          {activeTab === "detect" && (
            <>
              <section className="shell-hero">
                <div>
                  <div className="eyebrow-container">
                    <span className="eyebrow">Step 2: Detection</span>
                    <span className="status-badge status-badge--processing">
                      {sessionId ? "Ready" : "Waiting"}
                    </span>
                  </div>
                  <h1>Detect headings and subheadings</h1>
                  <p className="hero-copy">
                    The system automatically identifies the hierarchical structure of your PDF. It
                    detects headings, subheadings, and their relationships to build a logical
                    document tree.
                  </p>
                </div>
              </section>
              <div className="progress-section">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: sessionId ? "100%" : "35%" }} />
                </div>
                <p className="progress-text">
                  {sessionId
                    ? "Document parsed. Pull a preview of detected headings."
                    : "Upload and process your PDF to start detection."}
                </p>
                <div className="preview-actions">
                  <button
                    className="primary-button"
                    onClick={handleDetectPreview}
                    disabled={!sessionId || detectLoading}
                  >
                    {detectLoading ? "Fetching…" : "Fetch detected outline"}
                  </button>
                  <button className="ghost-button" onClick={() => setActiveTab("extract")} disabled={!sessionId}>
                    Go to Extraction
                  </button>
                </div>
                {detectError && <div className="upload-error">{detectError}</div>}
              </div>
              <div className="detection-preview">
                <h3 className="preview-title">Detected Structure Preview</h3>
                <div className="structure-tree">
                  {detectionPreview ? (
                    detectionPreview.split("\n").map((line, idx) => (
                      <div key={idx} className="tree-item">
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="placeholder-text">
                      No preview yet. Fetch the outline once your PDF is processed.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === "extract" && (
            <>
              <section className="shell-hero">
                <div>
                  <div className="eyebrow-container">
                    <span className="eyebrow">Step 3: Extraction</span>
                    <span className="status-badge status-badge--processing">
                      {sessionId ? "Ready" : "Waiting"}
                    </span>
                  </div>
                  <h1>Identify content blocks</h1>
                  <p className="hero-copy">
                    Content blocks under each section are identified and organized. The system
                    maintains logical nesting to preserve the original document layout and structure.
                  </p>
                </div>
              </section>
              <div className="progress-section">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: sessionId ? "100%" : "35%" }} />
                </div>
                <p className="progress-text">
                  {sessionId
                    ? "Pull a summarized view of extracted content blocks."
                    : "Upload and process your PDF to extract content."}
                </p>
                <div className="preview-actions">
                  <button
                    className="primary-button"
                    onClick={handleExtractPreview}
                    disabled={!sessionId || extractLoading}
                  >
                    {extractLoading ? "Fetching…" : "Fetch extraction summary"}
                  </button>
                  <button className="ghost-button" onClick={() => setActiveTab("chatbot")}>Go to Chatbot</button>
                </div>
                {extractError && <div className="upload-error">{extractError}</div>}
              </div>
              <div className="detection-preview">
                <h3 className="preview-title">Extracted Content Overview</h3>
                <div className="structure-tree">
                  {extractionPreview ? (
                    extractionPreview.split("\n").map((line, idx) => (
                      <div key={idx} className="tree-item">
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="placeholder-text">
                      No extraction summary yet. Fetch it once your PDF is processed.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === "chatbot" && (
            <>
              <section className="shell-hero">
                <div>
                  <div className="eyebrow-container">
                    <span className="eyebrow">Assistant</span>
                    <span
                      className={`status-badge ${
                        isProcessingStarted ? "status-badge--success" : "status-badge--ready"
                      }`}
                    >
                      {isProcessingStarted ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <h1>Document Analysis Assistant</h1>
                  <p className="hero-copy">
                    Get assistance with PDF structure extraction, ask questions about detected elements,
                    understand the extraction process, or learn about the output format. The assistant is
                    available after you process a document.
                  </p>
                </div>
              </section>

              {!isProcessingStarted ? (
                <div className="chatbot-inactive">
                  <div className="inactive-message">
                    <div className="inactive-icon" />
                    <h3>Assistant Not Available</h3>
                    <p>Please upload a PDF file and click "Process File" to activate the assistant.</p>
                    <button
                      className="primary-button"
                      onClick={() => setActiveTab("upload")}
                      style={{ marginTop: "20px" }}
                    >
                      Go to Upload
                    </button>
                  </div>
                </div>
              ) : (
                <div className="chatbot-container">
                  <div className="chat-messages">
                    {messages.length === 0 ? (
                      <div className="chat-message chat-message--bot">
                        <div className="chat-avatar">
                          <div className="avatar avatar--bot" />
                        </div>
                        <div className="chat-content">
                          <p>Initializing assistant...</p>
                        </div>
                      </div>
                    ) : (
                      messages.map((message) => (
                        <div
                          key={message.id}
                          className={`chat-message ${
                            message.sender === "bot" ? "chat-message--bot" : "chat-message--user"
                          }`}
                        >
                          <div className="chat-avatar">
                            {message.sender === "bot" ? (
                              <div className="avatar avatar--bot" />
                            ) : (
                              <div className="avatar avatar--user" />
                            )}
                          </div>
                          <div className="chat-content">
                            <p>{message.text}</p>
                            {message.sender === "bot" && message.references && message.references.length > 0 && (
                              <div className="chat-refs">
                                <strong>References:</strong>
                                <ul>
                                  {message.references.slice(0, 4).map((ref, idx) => (
                                    <li key={idx}>
                                      Page {ref.page} – {ref.section}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    )}

                    {chatError && <div className="upload-error">{chatError}</div>}
                  </div>
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
              )}
            </>
          )}

          {activeTab === "settings" && (
            <>
              <section className="shell-hero">
                <div>
                  <p className="eyebrow">Configuration</p>
                  <h1>System settings</h1>
                  <p className="hero-copy">
                    Configure detection sensitivity, output format preferences, and processing options.
                  </p>
                </div>
              </section>
              <div className="settings-grid">
                <div className="setting-card">
                  <h3>Detection Sensitivity</h3>
                  <div className="slider-container">
                    <input type="range" min="1" max="10" defaultValue="7" className="slider" />
                    <div className="slider-labels">
                      <span>Low</span>
                      <span>High</span>
                    </div>
                  </div>
                </div>
                <div className="setting-card">
                  <h3>Output Format</h3>
                  <div className="radio-group">
                    <label className="radio-option">
                      <input type="radio" name="format" defaultChecked />
                      <span>Pretty JSON</span>
                    </label>
                    <label className="radio-option">
                      <input type="radio" name="format" />
                      <span>Minified JSON</span>
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}

          <section className="card-grid">
            <article className="card-large">
              <div className="card-header">
                <p className="eyebrow eyebrow-muted">Why this matters</p>
                <h2>Deliver PDFs as structured, reliable JSON</h2>
              </div>
              <p className="card-description">
                Turn messy PDF layouts into organized data you can trust. Preserve hierarchy, keep headings
                and content paired, and export cleanly for downstream workflows.
              </p>
              <div className="requirements-section">
                <h3 className="requirements-title">Design principles</h3>
                <ul className="requirements-list">
                  <li>Keep heading depth and order intact</li>
                  <li>Attach paragraphs and tables to the correct section</li>
                  <li>Produce legible JSON that mirrors the document outline</li>
                  <li>Make it easy to review before exporting</li>
                </ul>
              </div>
            </article>
            <article className="card card-feature">
              <p className="eyebrow eyebrow-muted">Ingestion</p>
              <h3>Document intake</h3>
              <ul className="feature-list">
                <li>Drag-and-drop uploads up to 50MB</li>
                <li>Immediate validation with clear errors</li>
                <li>Single-click processing when you are ready</li>
              </ul>
            </article>
            <article className="card card-feature">
              <p className="eyebrow eyebrow-muted">Extraction</p>
              <h3>Structure insight</h3>
              <ul className="feature-list">
                <li>Outline preview before export</li>
                <li>Chat to cross-check sections and content</li>
                <li>JSON output aligned to the detected hierarchy</li>
              </ul>
            </article>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
