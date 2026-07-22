import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChat } from '../hooks/useChat'

export default function Chat() {
  const { messages, input, setInput, busy, scrollRef, handleSend } = useChat()

  return (
    <div className="card chat-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="label">Finance Assistant</div>
        <Link to="/chat" className="ghost" style={{ fontSize: 12, textDecoration: 'none', padding: '4px 10px' }}>
          Expand ↗
        </Link>
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
  )
}