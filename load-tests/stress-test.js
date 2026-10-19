import http from 'k6/http';
import { check } from 'k6';

export const options = { stages: [{ duration: '30s', target: 20 }, { duration: '1m', target: 50 }, { duration: '30s', target: 0 }] };

export default function () {
  const response = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/health/live`);
  check(response, { 'liveness returns 200': (res) => res.status === 200 });
}