import { useEffect, useRef, useState } from "react";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const getMainKeyword = (text = "", question = "") => {
  const keywordMatchers = [
    /\b\d+[\s-]*(?:day|month|year|week)s?\b/i,
    /\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\s+(?:day|month|year|week)s?\b/i,
    /\b\d+%\b/i,
    /\b\$?\d+(?:,\d{3})*(?:\.\d+)?\b/i,
  ];

  for (const pattern of keywordMatchers) {
    const match = text.match(pattern);
    if (match) return match[0];
  }

  const questionKeywords = question
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .filter((word) => word.length > 3);

  questionKeywords.sort((a, b) => b.length - a.length);

  for (const keyword of questionKeywords) {
    const match = text.match(new RegExp(`\\b${escapeRegExp(keyword)}\\b`, "i"));
    if (match) return match[0];
  }

  return null;
};

const renderMessageText = (message) => {
  if (message.sender !== "bot") return message.text;

  const keyword = getMainKeyword(message.text, message.question);
  if (!keyword) return message.text;

  const segments = message.text.split(new RegExp(`(${escapeRegExp(keyword)})`, "gi"));

  return segments.map((segment, idx) => {
    if (segment.toLowerCase() === keyword.toLowerCase()) {
      return (
        <strong key={`${message.id}-kw-${idx}`}>{segment}</strong>
      );
    }
    return <span key={`${message.id}-seg-${idx}`}>{segment}</span>;
  });
};

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
  const [referencePreview, setReferencePreview] = useState(null);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [videoStatus, setVideoStatus] = useState("idle");
  const [videoError, setVideoError] = useState("");

  const hidePreviewTimeoutRef = useRef(null);

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

  useEffect(() => {
    return () => {
      if (hidePreviewTimeoutRef.current) {
        clearTimeout(hidePreviewTimeoutRef.current);
      }
      if (pdfPreviewUrl) {
        URL.revokeObjectURL(pdfPreviewUrl);
      }
    };
  }, [pdfPreviewUrl]);

  const resetPdfPreviewUrl = () => {
    if (pdfPreviewUrl) {
      URL.revokeObjectURL(pdfPreviewUrl);
      setPdfPreviewUrl(null);
    }
  };

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
      resetPdfPreviewUrl();
      const objectUrl = URL.createObjectURL(file);
      setPdfPreviewUrl(objectUrl);
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

  const handleReferenceHover = (reference) => {
    if (hidePreviewTimeoutRef.current) {
      clearTimeout(hidePreviewTimeoutRef.current);
      hidePreviewTimeoutRef.current = null;
    }
    setReferencePreview(reference);
  };

  const handleReferenceLeave = () => {
    hidePreviewTimeoutRef.current = setTimeout(() => {
      setReferencePreview(null);
      hidePreviewTimeoutRef.current = null;
    }, 120);
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
    resetPdfPreviewUrl();
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

      const mappedReferences = (data.references || []).map((ref) => {
        const page =
          ref.page ||
          ref.pagenumber ||
          ref.pageNumber ||
          ref.Page ||
          ref.page_num;
        const pageFragment = page ? `#page=${page}` : "";
        const previewUrl = ref.url || (pdfPreviewUrl ? `${pdfPreviewUrl}${pageFragment}` : null);

        return {
          ...ref,
          page,
          url: previewUrl,
        };
      });

      const botMessage = {
        id: Date.now() + 1,
        text: data.answer || "No answer returned.",
        sender: "bot",
        references: mappedReferences,
        question: userText,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      setChatError(err.message || "Failed to get answer from backend.");
    } finally {
      setIsAsking(false);
    }
  };

  const latestBotConclusion = [...messages]
    .reverse()
    .find((msg) => msg.sender === "bot" && msg.text);

  useEffect(() => {
    setVideoStatus("idle");
    setVideoUrl("");
    setVideoError("");
  }, [latestBotConclusion?.id]);

  const handleGenerateVideo = async () => {
    if (!latestBotConclusion) {
      setVideoError("Ask a question and get a conclusion before generating video.");
      return;
    }

    setVideoStatus("loading");
    setVideoError("");
    setVideoUrl("");

    try {
      const res = await fetch(`${BACKEND_URL}/hackrx/generate_video`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: latestBotConclusion.text }),
      });

      if (!res.ok) {
        let detail = `Video request failed with status ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {}
        throw new Error(detail);
      }

      const data = await res.json();
      const url = data.video_url || data.url || data.output_url;

      if (!url) {
        throw new Error("No video URL returned by FAL.");
      }

      setVideoUrl(url);
      setVideoStatus("success");
    } catch (err) {
      console.error(err);
      setVideoStatus("error");
      setVideoError(err.message || "Failed to generate video.");
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
    resetPdfPreviewUrl();
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
              <div className="chat-layout">
                <div
                  className={`reference-preview-panel ${referencePreview ? "visible" : ""}`}
                  onMouseEnter={() => {
                    if (hidePreviewTimeoutRef.current) {
                      clearTimeout(hidePreviewTimeoutRef.current);
                      hidePreviewTimeoutRef.current = null;
                    }
                  }}
                  onMouseLeave={handleReferenceLeave}
                >
                  {referencePreview ? (
                    <>
                      <div className="reference-preview-header">
                        <p className="preview-label">PDF Preview</p>
                        <div className="preview-meta">
                          {referencePreview.page && (
                            <span className="preview-meta-item">Page {referencePreview.page}</span>
                          )}
                          {referencePreview.section && (
                            <span className="preview-meta-item">Section {referencePreview.section}</span>
                          )}
                        </div>
                        {referencePreview.url && (
                          <a
                            className="preview-link"
                            href={referencePreview.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open source PDF
                          </a>
                        )}
                      </div>
                      <div className="reference-preview-frame">
                        {referencePreview.url ? (
                          <iframe
                            src={referencePreview.url}
                            title="PDF preview"
                            className="reference-iframe"
                          />
                        ) : (
                          <div className="reference-preview-empty">
                            No preview available for this reference.
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="reference-preview-placeholder">
                      Hover over a reference to see the PDF context.
                    </div>
                  )}
                </div>

                <div className="chat-column">
                  <div className="chat-messages" ref={chatMessagesRef}>
                    {messages.map((msg) => (
                      <div key={msg.id} className={`message message-${msg.sender}`}>
                        <div className={`bubble bubble-${msg.sender}`}>
                          <p className="message-text">{renderMessageText(msg)}</p>
                          {msg.references?.length > 0 && (
                            <div className="references">
                              <p className="references-title">References</p>
                              <ul>
                                {msg.references.map((ref, idx) => (
                                  <li
                                    key={idx}
                                    onMouseEnter={() => handleReferenceHover(ref)}
                                    onMouseLeave={handleReferenceLeave}
                                  >
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

                  <div className="video-panel">
                    <div className="video-header">
                      <div>
                        <h3 className="video-title">Generate 8s Video</h3>
                        <p className="video-subtitle">Turn the latest conclusion into a short clip via FAL.ai's fast-svd model.</p>
                      </div>
                      <button
                        className="btn btn-secondary"
                        onClick={handleGenerateVideo}
                        disabled={!latestBotConclusion || videoStatus === "loading"}
                      >
                        {videoStatus === "loading" ? "Generating..." : "Create Video"}
                      </button>
                    </div>

                    {latestBotConclusion ? (
                      <p className="video-context">Using conclusion: {latestBotConclusion.text}</p>
                    ) : (
                      <p className="video-placeholder">Ask a question to produce a conclusion for video generation.</p>
                    )}

                    {videoError && <div className="error-message video-error">{videoError}</div>}

                    {videoStatus === "success" && videoUrl && (
                      <div className="video-preview">
                        <video className="video-player" src={videoUrl} controls></video>
                        <a className="video-link" href={videoUrl} target="_blank" rel="noreferrer">
                          Open video in new tab
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              </div>
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