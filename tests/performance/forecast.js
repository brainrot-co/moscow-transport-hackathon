import {
  checkForecast,
  requestForecast,
  setupContext,
} from './common.js';

export const options = {
  scenarios: {
    forecast_capacity: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { target: 100, duration: '2m' },
        { target: 200, duration: '2m' },
        { target: 300, duration: '2m' },
        { target: 400, duration: '2m' },
        { target: 500, duration: '2m' },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:forecast}': ['p(95)<300', 'p(99)<500'],
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
