import axios from "axios";

// Local backend — fallback to localhost if not explicitly set
const HOST = window.location.hostname;
const BASE = process.env.REACT_APP_API_URL || `http://${HOST}:8000/api`;

// Fast client — for instant initial render (~3-6s, 25s safety margin)
const fastClient = axios.create({ baseURL: BASE, timeout: 25000 });

// Base client — default 20s timeout suits most endpoints
const client = axios.create({ baseURL: BASE, timeout: 20000 });

// Heavy endpoints that do concurrent multi-source fetching
const heavyClient = axios.create({ baseURL: BASE, timeout: 35000 });

// Light endpoints (market-context is now concurrent on backend, should be ≤15s)
const lightClient = axios.create({ baseURL: BASE, timeout: 20000 });

// Retry helper — retries once on network connectivity errors only
function withRetry(axiosInstance) {
  axiosInstance.interceptors.response.use(
    (res) => res,
    async (err) => {
      const config = err.config;
      if (!config._retry && (err.code === "ERR_NETWORK" || err.code === "ECONNABORTED" || err.message === "Network Error")) {
        config._retry = true;
        // Wait 1s before retrying to allow network to stabilize
        await new Promise(resolve => setTimeout(resolve, 1000));
        return axiosInstance(config);
      }
      return Promise.reject(err);
    }
  );
  return axiosInstance;
}
withRetry(fastClient);
withRetry(client);
withRetry(heavyClient);
withRetry(lightClient);

const get       = (url, config={}) => client.get(url, config).then(r => r.data);
const getFast   = (url, config={}) => fastClient.get(url, config).then(r => r.data);
const getHeavy  = (url, config={}) => heavyClient.get(url, config).then(r => r.data);
const getLight  = (url, config={}) => lightClient.get(url, config).then(r => r.data);

export const api = {
  // Market overview
  getMarket:          (config={})              => getLight("/market", config),
  // market-context now runs all 3 fetchers concurrently on backend (≤12s each)
  getMarketContext:   (config={})              => getLight("/market-context", config),

  // FAST Signal — core OHLC only, ~3s response
  getFastSignal:      (symbol, interval="5m", config={}) => getFast(`/fast-signal/${symbol}/${interval || "5m"}`, config),

  // Signal Desk — full: primary download + 8 parallel external fetchers
  getSignalDesk:      (symbol, interval="1d", config={}) => getHeavy(`/signal-desk/${symbol}/${interval || "1d"}`, config),

  // Quant MTF Engine
  getQuant:           (symbol, config={})               => getHeavy(`/quant/${symbol}`, config),
  getQuantScanNifty:  (config={})                     => getHeavy("/quant/scan/nifty50", config),
  getQuantScanIndices:(config={})                     => getHeavy("/quant/scan/indices", config),

  // Options
  getOptions:         (symbol, config={})               => get(`/options/${symbol}`, config),

  // Screener — heavy because it scans Nifty50
  getScreener:        (config={})                     => getHeavy("/screener", config),

  // Institutional Flow Detection
  getInstitutionalAlerts: (symbol, config={}) => getFast(`/institutional/${symbol}`, config),

  // Gamma Squeeze Detection
  getGammaSqueeze: (symbol, config={}) => getFast(`/gamma-squeeze/${symbol}`, config),

  // Pipeline Intelligence
  getPipeline: (symbol, interval="15m", config={}) => getHeavy(`/pipeline/${symbol}?interval=${interval}`, config),
  getProbability: (symbol, interval="15m", config={}) => get(`/pipeline/probability/${symbol}?interval=${interval}`, config),
  getRegime: (symbol, interval="15m", config={}) => getFast(`/pipeline/regime/${symbol}?interval=${interval}`, config),
  getLLMAnalysis: (symbol, config={}) => getHeavy(`/pipeline/llm-analysis/${symbol}`, config),
  getPipelineStatus: (config={}) => getLight(`/pipeline/status`, config),

  // Explainability & Alpha Discovery
  getStageContributions: (symbol, page=1, limit=50, config={}) => get(`/explainability/stage-contributions?symbol=${symbol || ''}&page=${page}&limit=${limit}`, config),
  getAblationResults:    (symbol, page=1, limit=50, config={}) => get(`/explainability/ablation-results?symbol=${symbol || ''}&page=${page}&limit=${limit}`, config),
  getRegimePerformance:  (symbol, page=1, limit=50, config={}) => get(`/explainability/regime-performance?symbol=${symbol || ''}&page=${page}&limit=${limit}`, config),
  getFeatureDrift:       (symbol, page=1, limit=50, config={}) => get(`/explainability/feature-drift?symbol=${symbol || ''}&page=${page}&limit=${limit}`, config),
  getSignalExplanations: (symbol, start_date='', end_date='', page=1, limit=50, config={}) => get(`/explainability/signal-explanations?symbol=${symbol || ''}&start_date=${start_date}&end_date=${end_date}&page=${page}&limit=${limit}`, config),
  getAlphaLeaderboard:   (page=1, limit=50, config={}) => get(`/explainability/alpha-leaderboard?page=${page}&limit=${limit}`, config),
  getResearchSummary:    (symbol, config={}) => get(`/explainability/research-summary?symbol=${symbol || ''}`, config),

  // Cache management
  getCacheStatus:     ()                      => get("/cache/status"),
  clearCache:         ()                      => client.post("/cache/clear").then(r => r.data),

  // V7.4 Scheduler
  getSchedulerStatus: ()                      => getFast("/pipeline/scheduler-status"),

  // V8.0 Aggregated Dashboard (single endpoint for full dashboard state)
  getDashboard: (symbol, interval="15m")      => getHeavy(`/dashboard/${symbol}?interval=${interval}`),

  // V8.0 Platform Metrics
  getMetrics: ()                              => get("/metrics"),
};