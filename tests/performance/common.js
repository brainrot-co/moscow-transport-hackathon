import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const USERNAME = __ENV.K6_USERNAME || 'demo';
const PASSWORD = __ENV.K6_PASSWORD || 'demo-transport';

function formBody(values) {
  return Object.entries(values)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

function login() {
  const response = http.post(
    `${BASE_URL}/api/v1/login`,
    formBody({ username: USERNAME, password: PASSWORD }),
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      tags: { endpoint: 'login' },
    },
  );

  check(response, {
    'login succeeded': (result) => result.status === 200,
  });

  if (response.status !== 200) {
    throw new Error(`Login failed: ${response.status} ${response.body}`);
  }

  return response.json('access_token');
}

export function setupContext() {
  const token = __ENV.K6_TOKEN || login();
  const headers = { Authorization: `Bearer ${token}` };
  const response = http.get(`${BASE_URL}/api/v1/forecast/meta`, {
    headers,
    tags: { endpoint: 'forecast-meta' },
  });

  check(response, {
    'forecast meta succeeded': (result) => result.status === 200,
    'forecast is available': (result) => {
      try {
        return result.json('available') === true;
      } catch {
        return false;
      }
    },
  });

  if (response.status !== 200 || response.json('available') !== true) {
    throw new Error(`Forecast is unavailable: ${response.body}`);
  }

  const now = response.json('now');
  if (!now) {
    throw new Error('Forecast meta does not contain now');
  }

  const day = now.slice(0, 10);
  return {
    token,
    dateFrom: `${day}T00:00:00+03:00`,
    dateTo: `${day}T23:00:00+03:00`,
    date: day,
  };
}

function headers(data) {
  return { Authorization: `Bearer ${data.token}` };
}

function validForecast(response) {
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
}

export function requestForecast(data) {
  return http.get(
    `${BASE_URL}/api/v1/forecast` +
      `?date_from=${encodeURIComponent(data.dateFrom)}` +
      `&date_to=${encodeURIComponent(data.dateTo)}` +
      '&granularity=hour',
    { headers: headers(data), tags: { endpoint: 'forecast' } },
  );
}

export function checkForecast(response) {
  return check(response, {
    'forecast status is 200': (result) => result.status === 200,
    'forecast response is valid': validForecast,
  });
}

export function requestLoad(data) {
  return http.get(
    `${BASE_URL}/api/v1/forecast/load?date=${encodeURIComponent(data.date)}`,
    { headers: headers(data), tags: { endpoint: 'forecast-load' } },
  );
}

export function checkLoad(response, data) {
  return check(response, {
    'load status is 200': (result) => result.status === 200,
    'load response is valid': (result) => {
      try {
        const body = result.json();
        return body.schema_version === 1 &&
          body.date === data.date &&
          body.meta?.available === true &&
          Array.isArray(body.data);
      } catch {
        return false;
      }
    },
  });
}

export function requestAnalytics(data) {
  return http.get(
    `${BASE_URL}/api/v1/forecast/analytics?date=${encodeURIComponent(data.date)}&routes=7`,
    { headers: headers(data), tags: { endpoint: 'forecast-analytics' } },
  );
}

export function checkAnalytics(response, data) {
  return check(response, {
    'analytics status is 200': (result) => result.status === 200,
    'analytics response is valid': (result) => {
      try {
        const body = result.json();
        return body.schema_version === 1 &&
          body.date === data.date &&
          body.meta?.available === true &&
          Array.isArray(body.hours) &&
          Array.isArray(body.routes);
      } catch {
        return false;
      }
    },
  });
}

export function requestPreview(data) {
  return http.post(
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
        ...headers(data),
        'Content-Type': 'application/json',
      },
      tags: { endpoint: 'forecast-preview' },
    },
  );
}

export function checkPreview(response) {
  return check(response, {
    'preview status is 200': (result) => result.status === 200,
    'preview response is valid': (result) => {
      try {
        const body = result.json();
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
}
