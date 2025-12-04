import { useState, useRef, useEffect } from "react";
import "./App.css";

const BACKEND_URL = "http://localhost:8000";

function App() {
  const [activeTab, setActiveTab] = useState("upload");
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [isProcessingStarted, setIsProcessingStarted] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [chatError, setChatError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (isProcessingStarted && messages.length === 0) {
      setMessages([
        {
          id: 1,
          text: "Your PDF is ready. Ask me questions about coverage, exclusions, grace periods, waiting periods, and more. All answers are strictly grounded in the document.",
          sender: "bot",
        },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProcessingStarted]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      setUploadError("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setUploadedFile(file);
      setUploadError("");
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
      setActiveTab("chatbot");

      setMessages([
        {
          id: 1,
          text: "I’ve parsed your PDF. Ask any policy question — I’ll answer using exact wording from the document wherever possible.",
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

      const data = await res.json(); // { question, answer, references }

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

  return (
    <div className="app-root">
      <div className="app-shell">
        {/* Sidebar */}
        <aside className="shell-sidebar">
          <div className="logo-block">
            <div className="logo-mark">HR</div>
            <div className="logo-text">
              <div className="logo-title">HackRx CORE</div>
              <div className="logo-subtitle">Policy Intelligence Engine</div>
            </div>
          </div>

          <nav className="nav">
            <div className="nav-group">
              <div className="nav-label">Workflow</div>
              <button
                className={`nav-item ${
                  activeTab === "upload" ? "nav-item--active" : ""
                }`}
                onClick={() => handleTabChange("upload")}
              >
                <span className="nav-dot" />
                Upload PDF
              </button>
              <button
                className={`nav-item ${
                  activeTab === "structure" ? "nav-item--active" : ""
                }`}
                onClick={() => handleTabChange("structure")}
              >
                <span className="nav-dot" />
                Detect Structure
              </button>
              <button
                className={`nav-item ${
                  activeTab === "content" ? "nav-item--active" : ""
                }`}
                onClick={() => handleTabChange("content")}
              >
                <span className="nav-dot" />
                Extract Content
              </button>
              <button
                className={`nav-item ${
                  activeTab === "chatbot" ? "nav-item--active" : ""
                }`}
                onClick={() => handleTabChange("chatbot")}
              >
                <span className="nav-dot" />
                Chatbot
              </button>
            </div>

            <div className="nav-group nav-group--secondary">
              <div className="nav-label">Backend</div>
              <div className="nav-status">
                <span className="status-dot status-dot--online" />
                <span className="status-text">
                  FastAPI at <code>http://localhost:8000</code>
                </span>
              </div>
            </div>
          </nav>
        </aside>

        {/* Main body */}
        <div className="shell-body">
          {/* Header */}
          <header className="shell-header">
            <div>
              <h1 className="page-title">HackRx CORE Assistant</h1>
              <p className="page-subtitle">
                Upload an insurance policy PDF once, then query it using a
                policy-aware assistant backed by your FastAPI service.
              </p>
            </div>
          </header>

          {/* Content area */}
          <main className="shell-content">
            {activeTab === "upload" && (
              <section className="panel panel-main">
                <div className="panel-header">
                  <h2>1. Upload Policy PDF</h2>
                  <p>Drop a health-insurance policy PDF to begin analysis.</p>
                </div>

                <div
                  className={`upload-dropzone ${
                    isDragging ? "upload-dropzone--dragging" : ""
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={handleFileClick}
                >
                  <input
                    type="file"
                    accept="application/pdf"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    onChange={handleFileChange}
                  />
                  <div className="dropzone-inner">
                    <div className="dropzone-icon" />
                    <div className="dropzone-text">
                      <strong>
                        {uploadedFile
                          ? uploadedFile.name
                          : "Click to browse or drag & drop PDF"}
                      </strong>
                      <span>Only policy PDFs are supported</span>
                    </div>
                  </div>
                </div>

                {uploadError && (
                  <div className="alert alert--error">{uploadError}</div>
                )}

                <div className="upload-actions">
                  <button
                    className="file-action-button file-action-button--primary"
                    onClick={handleProcessFile}
                    disabled={isUploading || !uploadedFile}
                  >
                    {isUploading ? "Processing…" : "Process File"}
                  </button>
                  <span className="upload-hint">
                    Once processed, the Chatbot tab will activate for
                    document-grounded Q&amp;A.
                  </span>
                </div>

                <div className="step-grid">
                  <div className="step-card">
                    <div className="step-number">1</div>
                    <div className="step-content">
                      <h3>Ingest &amp; Normalize</h3>
                      <p>
                        CORE reads raw PDF, analyzes fonts, layout and visual
                        hierarchy for policy-grade structure.
                      </p>
                    </div>
                  </div>
                  <div className="step-card">
                    <div className="step-number">2</div>
                    <div className="step-content">
                      <h3>Detect Coverage Logic</h3>
                      <p>
                        Section headings, exclusions, definitions and waiting
                        periods are tagged and grouped.
                      </p>
                    </div>
                  </div>
                  <div className="step-card">
                    <div className="step-number">3</div>
                    <div className="step-content">
                      <h3>Ask Anything</h3>
                      <p>
                        Use the Chatbot panel to query grace periods,
                        maternity, moratorium, and more – grounded only in your
                        policy.
                      </p>
                    </div>
                  </div>
                </div>
              </section>
            )}

            {activeTab === "structure" && (
              <section className="panel panel-main">
                <div className="panel-header">
                  <h2>2. Detect Structure</h2>
                  <p>
                    This view can later show the reconstructed section tree and
                    headings. For now, upload and process a PDF in step 1, then
                    explore via the Chatbot tab.
                  </p>
                </div>
              </section>
            )}

            {activeTab === "content" && (
              <section className="panel panel-main">
                <div className="panel-header">
                  <h2>3. Extract Content</h2>
                  <p>
                    This view can display normalized JSON of paragraphs,
                    coverage flags and exclusions extracted from the policy.
                  </p>
                </div>
              </section>
            )}

            {activeTab === "chatbot" && (
              <section className="panel panel-main chatbot-panel">
                <div className="panel-header">
                  <h2>4. Chat with the Policy</h2>
                  <p>
                    Ask precise policy questions. Answers are generated using
                    your policy PDF and Groq, with exact wording wherever
                    possible.
                  </p>
                </div>

                <div className="chatbot-layout">
                  <div className="chat-messages">
                    {messages.length === 0 ? (
                      <div className="chat-message chat-message--bot">
                        <div className="chat-avatar">
                          <div className="avatar avatar--bot" />
                        </div>
                        <div className="chat-content">
                          <p>
                            Upload and process a PDF in the first tab, then
                            come back here to start asking questions.
                          </p>
                        </div>
                      </div>
                    ) : (
                      messages.map((message) => (
                        <div
                          key={message.id}
                          className={`chat-message ${
                            message.sender === "bot"
                              ? "chat-message--bot"
                              : "chat-message--user"
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
                            {message.sender === "bot" &&
                              message.references &&
                              message.references.length > 0 && (
                                <div className="chat-refs">
                                  <strong>References:</strong>
                                  <ul>
                                    {message.references
                                      .slice(0, 4)
                                      .map((ref, idx) => (
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

                    {chatError && (
                      <div className="alert alert--error alert--compact">
                        {chatError}
                      </div>
                    )}
                  </div>

                  <div className="chat-input-row">
                    <input
                      type="text"
                      className="chat-input"
                      placeholder={
                        sessionId
                          ? "Ask about grace periods, exclusions, waiting periods, etc…"
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
                      disabled={
                        !inputMessage.trim() || !sessionId || isAsking
                      }
                    >
                      {isAsking ? "Thinking…" : "Send"}
                    </button>
                  </div>
                  <p className="chat-hint">
                    Tip: Press <kbd>Enter</kbd> to send once your PDF is
                    processed.
                  </p>
                </div>
              </section>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;
