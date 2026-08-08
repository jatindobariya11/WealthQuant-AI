import React, { Component, Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";

const Dashboard      = lazy(() => import('./pages/Dashboard'));
const Screener       = lazy(() => import('./pages/Screener'));
const StockDetail    = lazy(() => import('./pages/StockDetail'));
const Pipeline       = lazy(() => import('./pages/Pipeline'));
const Explainability = lazy(() => import('./pages/Explainability'));

const LoadingFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#a1a1aa', fontFamily: 'Inter' }}>
    Loading component...
  </div>
);

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "2rem", color: "#fff", background: "#050505", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", fontFamily: "'Inter', sans-serif" }}>
          <h2 style={{ color: "#ef4444", marginBottom: "1rem", fontWeight: 600 }}>Application Error</h2>
          <p style={{ color: "#a1a1aa", maxWidth: "600px", textAlign: "center", marginBottom: "2rem", lineHeight: "1.6" }}>
            {this.state.error ? this.state.error.toString() : "An unexpected error occurred during rendering."}
          </p>
          <button 
            onClick={() => window.location.reload()} 
            style={{ padding: "10px 24px", background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff", borderRadius: "8px", cursor: "pointer", fontWeight: 600 }}
            onMouseOver={(e) => e.target.style.background = "rgba(255,255,255,0.15)"}
            onMouseOut={(e) => e.target.style.background = "rgba(255,255,255,0.08)"}
          >
            Reload Platform
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Nav() {
  const loc = useLocation();
  const link = (to, label, icon) => (
    <Link to={to} style={{
      padding: "6px 14px", borderRadius: 8, fontSize: 14, fontWeight: 600,
      background: loc.pathname === to ? "rgba(255,255,255,0.1)" : "transparent",
      color:      loc.pathname === to ? "#fff"    : "#a1a1aa",
      display: "flex", alignItems: "center", gap: "6px",
      transition: "all 0.2s ease",
    }}>
      <span style={{ fontSize: "16px" }}>{icon}</span>
      {label}
    </Link>
  );
  return (
    <div style={{ background: "#050505", borderBottom: "1px solid rgba(255,255,255,0.08)",
      padding: "0 24px", display: "flex", alignItems: "center", height: 52, gap: 4 }}>
      <Link to="/" className="brand-font" style={{
        fontWeight: 700, fontSize: 18, marginRight: "auto", color: "#fff",
        letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "8px",
      }}>
        <span style={{
          background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>◆</span>
        WealthQuant
      </Link>
      {link("/",          "Dashboard", "📊")}
      {link("/screener",  "Screener",  "🔍")}
      {link("/pipeline",  "AI Pipeline", "🧠")}
      {link("/explainability", "Explainability", "🔬")}
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Nav />
        <div style={{ padding: 24 }}>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/"           element={<Dashboard />} />
              <Route path="/screener"   element={<Screener />} />
              <Route path="/stock/:sym" element={<StockDetail />} />
              <Route path="/pipeline"   element={<Pipeline />} />
              <Route path="/explainability" element={<Explainability />} />
            </Routes>
          </Suspense>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
