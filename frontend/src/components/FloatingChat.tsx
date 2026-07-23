import { useState } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '../context/ChatContext'

export default function FloatingChat() {
  const [open, setOpen] = useState(false)
  const { messages, input, setInput, busy, scrollRef, handleSend } = useChat()

  return (
    <>
      {open && (
        <div className="floating-chat-panel card">
          <div className="floating-chat-header">
            <span className="label">Finance Assistant</span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Link to="/chat" className="ghost" style={{ fontSize: 11, textDecoration: 'none', padding: '4px 8px' }}>
                Expand ↗
              </Link>
              <button className="ghost floating-chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
                ✕
              </button>
            </div>
          </div>

          <div className="chat-messages" ref={scrollRef}>
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble chat-bubble--${m.role}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            ))}
            {busy && <div className="chat-typing">Thinking…</div>}
          </div>

          <form className="chat-input-row" onSubmit={handleSend}>
            <input
              type="text"
              placeholder="Ask about a stock, index, or crypto…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button className="ghost" type="submit" disabled={busy}>Send</button>
          </form>
        </div>
      )}

      <button
        className="floating-chat-bubble"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? '✕' : '💬'}
      </button>
    </>
  )
}