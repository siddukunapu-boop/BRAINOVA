import React from 'react';

interface ErrorBoundaryState {
  error: Error | null;
}

interface ErrorFallbackProps {
  error: Error;
  onRetry: () => void;
}

/** Fallback UI shown instead of a blank page when a render error escapes a page component. */
export function ErrorFallback({ error, onRetry }: ErrorFallbackProps): React.ReactElement {
  const h = React.createElement;
  return h(
    'div',
    {
      role: 'alert',
      style: {
        minHeight: '60vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        padding: '24px',
        textAlign: 'center',
        color: 'var(--text-secondary)',
      },
    },
    h('h2', { style: { color: 'var(--text-primary)' } }, 'Something went wrong while displaying this page'),
    h('p', null, error.message || 'An unexpected rendering error occurred.'),
    h(
      'div',
      { style: { display: 'flex', gap: '10px' } },
      h('button', { type: 'button', className: 'btn btn-primary', onClick: onRetry }, 'Try again'),
      h(
        'button',
        { type: 'button', className: 'btn btn-secondary', onClick: () => window.location.reload() },
        'Reload page'
      )
    )
  );
}

export class ErrorBoundary extends React.Component<{ children?: React.ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // Never swallow: surface the error and component stack in the console.
    console.error('[BRAINOVA] Uncaught render error:', error, info.componentStack);
  }

  render(): React.ReactNode {
    if (this.state.error) {
      return React.createElement(ErrorFallback, {
        error: this.state.error,
        onRetry: () => this.setState({ error: null }),
      });
    }
    return this.props.children;
  }
}

