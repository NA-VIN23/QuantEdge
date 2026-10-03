import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { sendChatMessage, type ChatMessage } from '../../services/api';
import './AssistantPanel.css';

const SUGGESTED_PROMPTS = [
  'What is the final equity and total return?',
  'How did the walk-forward validation perform?',
  'What is the win rate and profit factor?',
  'Break down the stop-loss vs trend exits',
];

const LOADING_PHRASES = [
  'Gathering research artifacts...',
  'Analyzing backtest metrics...',
  'Verifying pipeline data...',
  'Formulating research response...',
  'Thinking...',
];

function formatMessageContent(text: string) {
  const lines = text.split('\n');
  return lines.map((line, lIdx) => {
    const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ');
    const content = isBullet ? line.trim().substring(2) : line;

    const parts = content.split(/(\*\*.*?\*\*|`.*?`)/g);
    const parsedLine = parts.map((part, pIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={pIdx}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={pIdx} className="chat-code">{part.slice(1, -1)}</code>;
      }
      return part;
    });

    if (isBullet) {
      return (
        <li key={lIdx} className="chat-bullet">
          {parsedLine}
        </li>
      );
    }

    if (!line.trim()) {
      return <div key={lIdx} className="chat-gap" />;
    }

    return (
      <p key={lIdx} className="chat-p">
        {parsedLine}
      </p>
    );
  });
}

export function AssistantPanel() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Extract symbol from pathname, e.g. /backtest/ITC -> ITC
  const pathParts = location.pathname.split('/').filter(Boolean);
  let currentSymbol = 'ITC';
  if (pathParts.length >= 2 && ['stocks', 'backtest', 'trades', 'data'].includes(pathParts[0])) {
    currentSymbol = pathParts[1].toUpperCase();
  }

  // Scroll to bottom on new messages
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, loadingStep]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 120);
    }
  }, [isOpen]);

  // Cycle loading phrases dynamically while waiting for response
  useEffect(() => {
    if (!isLoading) {
      setLoadingStep(0);
      return;
    }
    const timer = setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % LOADING_PHRASES.length);
    }, 1500);
    return () => clearInterval(timer);
  }, [isLoading]);

  // Context switch notification on route change
  useEffect(() => {
    if (messages.length > 0) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `[Switched context to ${currentSymbol}]` },
      ]);
      setSources([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSymbol]);

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content: textToSend.trim() };
    const newMessages = [...messages, userMessage];

    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setLoadingStep(0);
    setError(null);
    setSources([]);

    try {
      const response = await sendChatMessage({
        symbol: currentSymbol,
        messages: newMessages.filter((m) => !m.content.startsWith('[Switched context')),
      });

      setMessages((prev) => [...prev, { role: 'assistant', content: response.reply }]);
      setSources(response.sources);
    } catch (err: any) {
      setError(err.message || 'Unable to generate response.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const handleClear = () => {
    setMessages([]);
    setSources([]);
    setError(null);
  };

  const hasTyped = input.trim().length > 0;

  return (
    <div className="gpt-widget-container">
      {/* ── Floating Ball in Right Bottom (Mild White Theme) ── */}
      <button
        type="button"
        id="ai-assistant-ball"
        className={`gpt-floating-ball ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? 'Close chat' : 'Open AI Assistant'}
        aria-label="AI Assistant"
        aria-expanded={isOpen}
      >
        {isOpen ? (
          <svg className="ball-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <svg className="ball-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
        {/* Label for testing-library and accessibility */}
        <span className="gpt-ball-label">AI Assistant</span>
      </button>

      {/* ── ChatGPT-Inspired Chat Window (Mild White Theme) ── */}
      <div className={`gpt-chat-window ${isOpen ? 'visible' : 'hidden'}`} aria-hidden={!isOpen}>
        {/* Header */}
        <div className="gpt-header">
          <div className="gpt-header-left">
            <span className="gpt-header-title">QuantEdge Assistant</span>
            <span className="assistant-symbol-badge">{currentSymbol}</span>
          </div>
          <div className="gpt-header-right">
            {messages.length > 0 && (
              <button
                type="button"
                className="gpt-icon-btn"
                onClick={handleClear}
                title="New Chat"
                aria-label="New Chat"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
              </button>
            )}
            <button
              type="button"
              className="gpt-icon-btn"
              onClick={() => setIsOpen(false)}
              title="Close window"
              aria-label="Close Assistant"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Message Space */}
        <div className="gpt-messages-space">
          {messages.length === 0 && (
            <div className="gpt-empty-state">
              <div className="gpt-empty-logo">
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </div>
              <h3 className="gpt-empty-title">Research Assistant</h3>
              <p className="gpt-empty-sub">
                Ask about {currentSymbol} performance, exits, or validation metrics.
              </p>
              <div className="gpt-suggestions">
                {SUGGESTED_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="gpt-suggestion-btn"
                    onClick={() => handleSend(prompt)}
                    disabled={isLoading}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`gpt-row ${msg.role}`}>
              {msg.role === 'assistant' && (
                <div className="gpt-avatar">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                </div>
              )}
              <div className={`gpt-bubble ${msg.role}`}>
                {formatMessageContent(msg.content)}
              </div>
            </div>
          ))}

          {/* Dynamic Loading State with Loader and Changing Phrases */}
          {isLoading && (
            <div className="gpt-row assistant">
              <div className="gpt-avatar">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </div>
              <div className="gpt-bubble assistant gpt-loader-container">
                <svg className="gpt-spinner-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.2" />
                  <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                </svg>
                <span className="gpt-loader-text" key={loadingStep}>
                  {LOADING_PHRASES[loadingStep]}
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="gpt-error-box">
              <span>{error}</span>
            </div>
          )}

          <div ref={endOfMessagesRef} />
        </div>

        {/* Sources Footer */}
        {sources.length > 0 && (
          <div className="gpt-sources-row">
            <span className="gpt-sources-label">Sources:</span>
            {sources.map((s, idx) => (
              <span key={idx} className="gpt-source-pill">
                {s}
              </span>
            ))}
          </div>
        )}

        {/* ── Input Box: ChatGPT Capsule with Up-Arrow Send Button ── */}
        <div className="gpt-input-wrapper">
          <form className="gpt-input-capsule" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className="gpt-text-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask about ${currentSymbol}...`}
              disabled={isLoading}
            />
            {/* Signature ChatGPT Up-Arrow Send Button */}
            <button
              type="submit"
              className={`gpt-send-button ${hasTyped && !isLoading ? 'active' : ''}`}
              disabled={!hasTyped || isLoading}
              aria-label="Send Message"
              title="Send Message"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
