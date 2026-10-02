import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { sendChatMessage, type ChatMessage } from '../../services/api';
import './AssistantPanel.css';

export function AssistantPanel() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Extract symbol from pathname, e.g. /backtest/ITC -> ITC
  // Default to ITC if none is found to be safe.
  const pathParts = location.pathname.split('/').filter(Boolean);
  let currentSymbol = 'ITC';
  if (pathParts.length >= 2 && ['stocks', 'backtest', 'trades', 'data'].includes(pathParts[0])) {
      currentSymbol = pathParts[1].toUpperCase();
  }

  // Scroll to bottom on new messages
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Clear messages when symbol changes? Optionally we could.
  // Let's keep them for now, but maybe add a system notification.
  useEffect(() => {
    if (messages.length > 0) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `[Context switched to ${currentSymbol}]` }
      ]);
      setSources([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSymbol]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMessage];

    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setError(null);
    setSources([]);

    try {
      const response = await sendChatMessage({
        symbol: currentSymbol,
        messages: newMessages.filter(m => !m.content.startsWith('[Context switched')),
      });

      setMessages((prev) => [...prev, { role: 'assistant', content: response.reply }]);
      setSources(response.sources);
    } catch (err: any) {
      setError(err.message || 'An error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`assistant-panel ${isOpen ? 'open' : 'closed'}`}>
      <button className="assistant-toggle" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? 'Close Assistant' : 'AI Assistant'}
      </button>

      <div className="assistant-content">
        <div className="assistant-header">
          <h3>Research Assistant</h3>
          <span className="assistant-symbol-badge">{currentSymbol}</span>
        </div>

        <div className="assistant-messages">
          {messages.length === 0 && (
            <div className="assistant-empty">
              Ask me about {currentSymbol}'s performance, backtest, or validation results.
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}
          {isLoading && (
            <div className="message assistant loading">
              <div className="message-content">Thinking...</div>
            </div>
          )}
          {error && (
            <div className="assistant-error">
              {error}
            </div>
          )}
          <div ref={endOfMessagesRef} />
        </div>

        {sources.length > 0 && (
          <div className="assistant-sources">
            <strong>Sources:</strong>
            <ul>
              {sources.map((s, idx) => <li key={idx}>{s}</li>)}
            </ul>
          </div>
        )}

        <form className="assistant-input-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask about ${currentSymbol}...`}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
