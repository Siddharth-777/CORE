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
  const [activeTab, setActiveTab] = useState("chat");
  const [currentPage, setCurrentPage] = useState("landing");

  const fileInputRef = useRef(null);
  const chatMessagesRef = useRef(null);

  useEffect(() => {
    if (isProcessingStarted && messages.length === 0) {
      setMessages([
        {
          id: 1,
          text: "Your PDF is parsed. Ask about coverage, exclusions, grace periods, or waiting periods—answers stay grounded in the document.",
          sender: "bot",
        },
      ]);
    }
  }, [isProcessingStarted, messages.length]);

  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
    }
  }, [messages]);

  const validateFile = (file) => {
    if (file.type !== "application/pdf") {
      setUploadError("Please upload a PDF file only.");
      return false;
    }

    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError("File size exceeds 50MB limit.");
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
        } catch {}
        throw new Error(detail);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setIsProcessingStarted(true);

      setMessages([
        {
          id: 1,
          text: "Your PDF has been uploaded successfully. I can assist you with questions about the structure extraction process, detected elements, or the output format.",
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
        } catch {}
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
        } catch {}
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

  const handleGoToApp = () => {
    setCurrentPage("app");
  };

  const handleGoToLanding = () => {
    setCurrentPage("landing");
    setUploadedFile(null);
    setUploadError("");
    setIsProcessingStarted(false);
    setMessages([]);
    setSessionId(null);
    setDetectionPreview("");
    setExtractionPreview("");
    setActiveTab("chat");
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${Math.round((bytes / k ** i) * 100) / 100} ${sizes[i]}`;
  };

  if (currentPage === "landing") {
    return (
      <div className="app">
        <header className="header">
          <div className="header-inner">
            <div className="logo">
              <div className="logo-mark"></div>
              <span className="logo-text">CORE</span>
            </div>
          </div>
        </header>

        <main className="landing-page">
          <div className="landing-hero">
            <h1 className="landing-title">Document Structure Extraction</h1>
            <p className="landing-subtitle">
              Extract hierarchical structure from PDF documents. Analyze headings, content blocks, and document organization with precision.
            </p>
            <button className="btn btn-primary btn-large" onClick={handleGoToApp}>
              Get Started
            </button>
          </div>

          <div className="landing-features">
            <div className="feature-card">
              <h3 className="feature-title">Intelligent Parsing</h3>
              <p className="feature-description">
                Automatically detect and extract document structure, preserving hierarchical relationships between sections.
              </p>
            </div>
            <div className="feature-card">
              <h3 className="feature-title">AI Assistant</h3>
              <p className="feature-description">
                Ask questions about document content and structure. Get contextual answers grounded in the source material.
              </p>
            </div>
            <div className="feature-card">
              <h3 className="feature-title">Content Analysis</h3>
              <p className="feature-description">
                Review extracted outlines and content summaries. Verify structure before exporting to downstream systems.
              </p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo" onClick={handleGoToLanding} style={{ cursor: 'pointer' }}>
            <div className="logo-mark"></div>
            <span className="logo-text">CORE</span>
          </div>
          <nav className="tabs">
            <button 
              className={activeTab === "chat" ? "tab tab-active" : "tab"}
              onClick={() => setActiveTab("chat")}
            >
              Chatbot
            </button>
            <button 
              className={activeTab === "outline" ? "tab tab-active" : "tab"}
              onClick={() => setActiveTab("outline")}
            >
              Document Outline
            </button>
            <button 
              className={activeTab === "content" ? "tab tab-active" : "tab"}
              onClick={() => setActiveTab("content")}
            >
              Content Summary
            </button>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {activeTab === "chat" && (
          <div className="tab-content">
            {!sessionId ? (
              <div className="upload-center">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileInputChange}
                  accept=".pdf,application/pdf"
                  style={{ display: "none" }}
                />
                
                {!uploadedFile ? (
                  <div className="upload-container">
                    <h2 className="upload-title">Upload Document</h2>
                    <p className="upload-subtitle">
                      Upload and process a PDF document to start asking questions about its structure and content.
                    </p>
                    <div
                      className={isDragging ? "dropzone dropzone-active" : "dropzone"}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onDrop={handleDrop}
                      onClick={(e) => {
                        if (e.target.tagName !== "BUTTON") {
                          handleChooseFileClick();
                        }
                      }}
                    >
                      <div className="dropzone-icon"></div>
                      <p className="dropzone-text">Drop PDF or click to browse</p>
                      <button
                        className="btn btn-secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleChooseFileClick();
                        }}
                      >
                        Select File
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="upload-container">
                    <h2 className="upload-title">Process Document</h2>
                    <p className="upload-subtitle">
                      Review your file and click process to begin extraction.
                    </p>
                    <div className="file-card-center">
                      <div className="file-header">
                        <div className="file-icon">
                          <div className="pdf-icon"></div>
                        </div>
                        <div className="file-details">
                          <div className="file-name">{uploadedFile.name}</div>
                          <div className="file-size">{formatFileSize(uploadedFile.size)}</div>
                        </div>
                      </div>
                      <div className="file-actions-center">
                        <button
                          className="btn btn-primary"
                          onClick={handleProcessFile}
                          disabled={isUploading}
                        >
                          {isUploading ? "Processing..." : "Process Document"}
                        </button>
                        <button className="btn btn-text" onClick={handleRemoveFile}>
                          Remove File
                        </button>
                      </div>
                    </div>
                    {uploadError && <div className="error-message">{uploadError}</div>}
                  </div>
                )}
              </div>
            ) : (
              <>
                <div className="chat-messages" ref={chatMessagesRef}>
                  {messages.map((msg) => (
                    <div key={msg.id} className={`message message-${msg.sender}`}>
                      <div className={`bubble bubble-${msg.sender}`}>
                        <p className="message-text">{msg.text}</p>
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

                  {isAsking && (
                    <div className="message message-bot">
                      <div className="bubble bubble-bot">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {chatError && <div className="error-message error-chat">{chatError}</div>}

                <div className="chat-input-wrapper">
                  <div className="input-container">
                    <input
                      type="text"
                      className="input"
                      placeholder="Ask about document structure, sections, or content..."
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === "Enter" && inputMessage.trim() && !isAsking) {
                          handleSendMessage();
                        }
                      }}
                      disabled={!sessionId || isAsking}
                    />
                    <button
                      className="btn btn-primary btn-icon"
                      onClick={handleSendMessage}
                      disabled={!inputMessage.trim() || !sessionId || isAsking}
                    >
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <path d="M18 2L9 11M18 2L12 18L9 11M18 2L2 8L9 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "outline" && (
          <div className="tab-content">
            <div className="preview-panel">
              <div className="preview-header">
                <div>
                  <h2 className="preview-title">Document Outline</h2>
                  <p className="preview-subtitle">
                    Hierarchical structure of headings and subheadings extracted from the PDF
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={handleDetectPreview}
                  disabled={!sessionId || detectLoading}
                >
                  {detectLoading ? "Loading..." : "Load Outline"}
                </button>
              </div>
              
              <div className="preview-content-large">
                {detectionPreview ? (
                  <div className="preview-text">
                    {detectionPreview.split("\n").map((line, idx) => (
                      <div key={idx} className="preview-line">
                        {line}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="preview-empty">
                    <p className="placeholder-text">
                      {sessionId 
                        ? "Click 'Load Outline' to view the document structure"
                        : "Process a document to view its hierarchical structure"
                      }
                    </p>
                  </div>
                )}
              </div>
              
              {detectError && <div className="error-message">{detectError}</div>}
            </div>
          </div>
        )}

        {activeTab === "content" && (
          <div className="tab-content">
            <div className="preview-panel">
              <div className="preview-header">
                <div>
                  <h2 className="preview-title">Content Summary</h2>
                  <p className="preview-subtitle">
                    Key content blocks organized by section hierarchy
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={handleExtractPreview}
                  disabled={!sessionId || extractLoading}
                >
                  {extractLoading ? "Loading..." : "Load Summary"}
                </button>
              </div>
              
              <div className="preview-content-large">
                {extractionPreview ? (
                  <div className="preview-text">
                    {extractionPreview.split("\n").map((line, idx) => (
                      <div key={idx} className="preview-line">
                        {line}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="preview-empty">
                    <p className="placeholder-text">
                      {sessionId 
                        ? "Click 'Load Summary' to view extracted content blocks"
                        : "Process a document to view its content summary"
                      }
                    </p>
                  </div>
                )}
              </div>
              
              {extractError && <div className="error-message">{extractError}</div>}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;