import { useState, useRef, useEffect } from 'react'
import { sendChatMessage, ChatMessage } from '../api'

export function useChat() {
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

  return { messages, input, setInput, busy, scrollRef, handleSend }
}