import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const USERNAME = __ENV.K6_USERNAME || 'demo';
const PASSWORD = __ENV.K6_PASSWORD || 'demo-transport';

export const options = {
  stages: [
    { duration: '1m', target: 5 },
    { duration: '2m', target: 10 },
    { duration: '3m', target: 25 },
    { duration: '3m', target: 50 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300', 'p(99)<500'],
    'http_req_failed{endpoint:forecast}': ['rate<0.01'],
    'http_req_failed{endpoint:forecast-load}': ['rate<0.01'],
    'http_req_failed{endpoint:forecast-analytics}': ['rate<0.01'],
    'http_req_failed{endpoint:forecast-preview}': ['rate<0.01'],
    'http_req_duration{endpoint:forecast}': ['p(95)<300', 'p(99)<500'],
    'http_req_duration{endpoint:forecast-load}': ['p(95)<300', 'p(99)<500'],
    'http_req_duration{endpoint:forecast-analytics}': ['p(95)<300', 'p(99)<500'],
    'http_req_duration{endpoint:forecast-preview}': ['p(95)<300', 'p(99)<500'],
    checks: ['rate>0.99'],
  },
};

export function setup() {
  const loginBody =
    `username=${encodeURIComponent(USERNAME)}` +
    `&password=${encodeURIComponent(PASSWORD)}`;
  const login = http.post(
    `${BASE_URL}/api/v1/login`,
    loginBody,
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      tags: { endpoint: 'login' },
    },
  );

  check(login, {
    'login succeeded': (response) => response.status === 200,
  });

  if (login.status !== 200) {
    throw new Error(`Login failed: ${login.status} ${login.body}`);
  }

  const token = login.json('access_token');
  const headers = {
    Authorization: `Bearer ${token}`,
  };

  const metaResponse = http.get(
    `${BASE_URL}/api/v1/forecast/meta`,
    { headers, tags: { endpoint: 'forecast-meta' } },
  );

  check(metaResponse, {
    'forecast meta succeeded': (response) => response.status === 200,
    'forecast is available': (response) => {
      try {
        return response.json('available') === true;
      } catch {
        return false;
      }
    },
  });

  if (metaResponse.status !== 200) {
    throw new Error(`Meta failed: ${metaResponse.status}`);
  }

  const now = metaResponse.json('now');

  if (!now) {
    throw new Error('Forecast meta does not contain now');
  }

  const day = now.slice(0, 10);

  return {
    token,
    dateFrom: `${day}T00:00:00+03:00`,
    dateTo: `${day}T23:00:00+03:00`,
  };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
  };

  const forecastUrl =
    `${BASE_URL}/api/v1/forecast` +
    `?date_from=${encodeURIComponent(data.dateFrom)}` +
    `&date_to=${encodeURIComponent(data.dateTo)}` +
    `&granularity=hour`;

  const forecast = http.get(forecastUrl, {
    headers,
    tags: { endpoint: 'forecast' },
  });

  check(forecast, {
    'forecast status is 200': (response) => response.status === 200,
    'forecast response is valid': (response) => {
      try {
        const body = response.json();
        return body.schema_version === 1 &&
          body.meta?.available === true &&
          Array.isArray(body.data) &&
          body.data.length > 0 &&
          body.query?.granularity === 'hour';
      } catch {
        return false;
      }
    },
  });

  const loadDate = data.dateFrom.slice(0, 10);
  const load = http.get(
    `${BASE_URL}/api/v1/forecast/load?date=${encodeURIComponent(loadDate)}`,
    {
      headers,
      tags: { endpoint: 'forecast-load' },
    },
  );

  check(load, {
    'load status is 200': (response) => response.status === 200,
    'load response is valid': (response) => {
      try {
        const body = response.json();
        return body.schema_version === 1 &&
          body.date === loadDate &&
          body.meta?.available === true &&
          Array.isArray(body.data);
      } catch {
        return false;
      }
    },
  });

  const analytics = http.get(
    `${BASE_URL}/api/v1/forecast/analytics?date=${encodeURIComponent(loadDate)}&routes=7`,
    {
      headers,
      tags: { endpoint: 'forecast-analytics' },
    },
  );

  check(analytics, {
    'analytics status is 200': (response) => response.status === 200,
    'analytics response is valid': (response) => {
      try {
        const body = response.json();
        return body.schema_version === 1 &&
          body.date === loadDate &&
          body.meta?.available === true &&
          Array.isArray(body.hours) &&
          Array.isArray(body.routes);
      } catch {
        return false;
      }
    },
  });

  const preview = http.post(
    `${BASE_URL}/api/v1/forecast/preview`,
    JSON.stringify({
      date_from: data.dateFrom,
      date_to: data.dateTo,
      routes: [7],
      granularity: 'hour',
      model_factors: { holiday: 0.7 },
      draft: [],
    }),
    {
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      tags: { endpoint: 'forecast-preview' },
    },
  );

  check(preview, {
    'preview status is 200': (response) => response.status === 200,
    'preview response is valid': (response) => {
      try {
        const body = response.json();
        return body.schema_version === 1 &&
          body.meta?.available === true &&
          Array.isArray(body.data) &&
          body.data.length > 0 &&
          body.query?.granularity === 'hour';
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}