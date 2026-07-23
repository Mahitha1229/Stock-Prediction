import { useState, ReactNode } from 'react'

interface Tab {
  id: string
  label: string
  content: ReactNode
}

export default function TickerTabs({ tabs }: { tabs: Tab[] }) {
  const [activeId, setActiveId] = useState(tabs[0]?.id)
  const activeTab = tabs.find((t) => t.id === activeId) ?? tabs[0]

  return (
    <div className="ticker-tabs">
      <div className="ticker-tabs__nav">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`ticker-tabs__btn ${tab.id === activeId ? 'ticker-tabs__btn--active' : ''}`}
            onClick={() => setActiveId(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="ticker-tabs__panel">
        {activeTab?.content}
      </div>
    </div>
  )
}