import http from 'k6/http';
import { check } from 'k6';
import { setupContext } from './common.js';

// /forecast без помощи кэша ответов: случайный день горизонта и случайный набор маршрутов,
// запросы почти не повторяются, поэтому каждый считается заново
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const ROUTES = [1, 7, 11, 12, 17, 25, 26, 28, 50];

export const options = {
  scenarios: {
    forecast_uncached: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.K6_UNCACHED_RPS || 50),
      timeUnit: '1s',
      duration: __ENV.K6_UNCACHED_DURATION || '60s',
      preAllocatedVUs: 50,
      maxVUs: 400,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
    dropped_iterations: ['count<10'],
  },
};

export function setup() {
  return setupContext();
}

export default function (data) {
  // горизонт демо-снапшота: 01.11–31.12.2025
  const day = new Date(Date.UTC(2025, 10, 1 + Math.floor(Math.random() * 61)))
    .toISOString()
    .slice(0, 10);
  const routes = ROUTES.filter(() => Math.random() < 0.5)
    .map((route) => `&routes=${route}`)
    .join('');
  const response = http.get(
    `${BASE_URL}/api/v1/forecast?date_from=${day}T00:00:00%2B03:00` +
      `&date_to=${day}T23:00:00%2B03:00&granularity=hour${routes}`,
    { headers: { Authorization: `Bearer ${data.token}` }, tags: { endpoint: 'forecast' } },
  );
  check(response, { 'forecast status is 200': (result) => result.status === 200 });
}
