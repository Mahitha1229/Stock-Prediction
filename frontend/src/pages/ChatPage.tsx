import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '../hooks/useChat'

export default function ChatPage() {
  const { messages, input, setInput, busy, scrollRef, handleSend } = useChat()

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand"><span className="brand__mark" />Quantis</div>
        <Link to="/" className="ghost" style={{ textDecoration: 'none' }}>← Back to Dashboard</Link>
      </div>

      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', padding: '24px' }}>
        <div className="card chat-panel chat-panel--full">
          <div className="label" style={{ marginBottom: 12 }}>Finance Assistant</div>
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
      </div>
    </div>
  )
}