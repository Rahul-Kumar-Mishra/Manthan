import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 1, iterations: 1 };

export default function () {
  const response = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/health/live`);
  check(response, { 'liveness returns 200': (res) => res.status === 200 });
}