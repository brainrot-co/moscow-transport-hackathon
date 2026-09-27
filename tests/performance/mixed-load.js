import {
  checkAnalytics,
  checkForecast,
  checkLoad,
  checkPreview,
  requestAnalytics,
  requestForecast,
  requestLoad,
  requestPreview,
  setupContext,
} from './common.js';

const duration = __ENV.K6_MIXED_DURATION || '5m';

export const options = {
  scenarios: {
    forecast: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_FORECAST_RPS || 210),
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 50,
      maxVUs: 300,
      exec: 'forecast',
    },
    load: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_LOAD_RPS || 45),
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 20,
      maxVUs: 100,
      exec: 'load',
    },
    analytics: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_ANALYTICS_RPS || 30),
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 20,
      maxVUs: 100,
      exec: 'analytics',
    },
    preview: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_PREVIEW_RPS || 15),
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 20,
      maxVUs: 100,
      exec: 'preview',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:forecast}': ['p(95)<300'],
    'http_req_duration{endpoint:forecast-load}': ['p(95)<300'],
    'http_req_duration{endpoint:forecast-analytics}': ['p(95)<300'],
    'http_req_duration{endpoint:forecast-preview}': ['p(95)<300'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count<10'],
  },
};

export function setup() {
  return setupContext();
}

export function forecast(data) {
  checkForecast(requestForecast(data));
}

export function load(data) {
  checkLoad(requestLoad(data), data);
}

export function analytics(data) {
  checkAnalytics(requestAnalytics(data), data);
}

export function preview(data) {
  checkPreview(requestPreview(data));
}
