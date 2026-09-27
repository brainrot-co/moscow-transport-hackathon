import {
  checkForecast,
  requestForecast,
  setupContext,
} from './common.js';

const rate = Number(__ENV.K6_SOAK_RPS || 200);
const duration = __ENV.K6_SOAK_DURATION || '60m';

export const options = {
  scenarios: {
    soak: {
      executor: 'constant-arrival-rate',
      rate,
      timeUnit: '1s',
      duration,
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:forecast}': ['p(95)<300'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count<10'],
  },
};

export function setup() {
  return setupContext();
}

export default function (data) {
  checkForecast(requestForecast(data));
}
