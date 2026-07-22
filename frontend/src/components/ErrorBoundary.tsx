import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to console for now; wire up to a logging service later if you want
    console.error('ErrorBoundary caught an error:', error, info)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 24,
            textAlign: 'center',
            color: 'var(--text-primary, #e6e6e6)',
            background: 'var(--bg, #0b0c10)',
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {this.props.fallbackTitle || 'Something went wrong'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-dim, #888)', maxWidth: 420 }}>
            {this.state.error?.message || 'An unexpected error occurred while rendering this section.'}
          </div>
          <button className="ghost" onClick={this.handleReload}>
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}