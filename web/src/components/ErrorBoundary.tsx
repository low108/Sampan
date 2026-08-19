import { Component, type ErrorInfo, type ReactNode } from 'react';

/* One component throwing must not blank the app.
 *
 * This is exactly how the map failure presented: Leaflet threw inside an
 * effect, React unmounted the whole tree, and the result was a white screen
 * with the real error only in the console. A judge, or an eighty-year-old,
 * sees nothing to act on. Now the archive says what broke and offers a reload.
 */
interface Props {
  children: ReactNode;
}
interface State {
  message: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { message: null };

  static getDerivedStateFromError(error: Error): State {
    return { message: error.message };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Sampan failed to render:', error, info.componentStack);
  }

  override render(): ReactNode {
    if (this.state.message === null) return this.props.children;
    return (
      <div className="failed">
        <h1>Sampan</h1>
        <p>Something went wrong drawing this page.</p>
        <p className="en">{this.state.message}</p>
        <div className="row" style={{ justifyContent: 'center' }}>
          <button className="btn" onClick={() => location.reload()}>
            Try again
          </button>
        </div>
      </div>
    );
  }
}
