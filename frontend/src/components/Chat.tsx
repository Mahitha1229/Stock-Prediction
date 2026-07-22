import { useState, useRef, useEffect } from 'react'
import { sendChatMessage, ChatMessage } from '../api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: "Hi! Ask me about any stock, index, or crypto — prices, fundamentals, trends, or predictions." },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, busy])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return

    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setInput('')
    setBusy(true)
    try {
      const reply = await sendChatMessage(text, messages)
      setMessages([...nextMessages, { role: 'assistant', content: reply }])
    } catch (err: any) {
      setMessages([...nextMessages, { role: 'assistant', content: 'Sorry, something went wrong reaching the assistant.' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card chat-panel">
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
  )
}