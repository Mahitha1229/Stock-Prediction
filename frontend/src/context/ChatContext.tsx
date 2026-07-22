import { createContext, useContext, useState, useRef, useEffect, ReactNode } from 'react'
import { sendChatMessage, ChatMessage } from '../api'

interface ChatContextValue {
  messages: ChatMessage[]
  input: string
  setInput: (v: string) => void
  busy: boolean
  scrollRef: React.RefObject<HTMLDivElement>
  handleSend: (e: React.FormEvent) => Promise<void>
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
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
    } catch {
      setMessages([...nextMessages, { role: 'assistant', content: 'Sorry, something went wrong reaching the assistant.' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <ChatContext.Provider value={{ messages, input, setInput, busy, scrollRef, handleSend }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within a ChatProvider')
  return ctx
}