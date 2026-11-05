"""Synthetic API workload. Requires an isolated test environment and seeded credentials."""
import itertools
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from locust import HttpUser, between, task
from locust.exception import StopUser

if os.environ.get('SEATLOCK_LOADTEST_ISOLATED') != 'yes':
    raise RuntimeError('Set SEATLOCK_LOADTEST_ISOLATED=yes only for an isolated synthetic test environment.')

fixture = json.loads((Path(__file__).resolve().parents[1] / '.loadtest' / 'accounts.json').read_text(encoding='utf-8'))
account_sequence = itertools.cycle(fixture['accounts'])
isolated_host = os.environ.get('SEATLOCK_LOADTEST_HOST', '').rstrip('/')
if not isolated_host:
    raise RuntimeError('Set SEATLOCK_LOADTEST_HOST to the isolated API URL.')


def require_isolated_target():
    try:
        with urlopen(isolated_host + '/internal/loadtest-guard', timeout=5) as response:
            allowed = json.load(response).get('synthetic_load_test') is True
    except Exception as exc:
        raise RuntimeError('Target did not identify itself as an isolated synthetic test environment.') from exc
    if not allowed:
        raise RuntimeError('Target did not identify itself as an isolated synthetic test environment.')


require_isolated_target()


class CarpoolUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        if (self.environment.host or '').rstrip('/') != isolated_host:
            raise StopUser()
        self.account = next(account_sequence)
        self.headers = {'Authorization': 'Bearer ' + self.account['token']}
        self.created_rides = []
        self.booking_code = None

    @task(8)
    def browse(self):
        self.client.get('/api/v1/rides', name='rides browse')

    @task(4)
    def search(self):
        self.client.get('/api/v1/rides?origin=Pune&destination=Nagpur', name='rides search')

    @task(5)
    def details(self):
        ride = random.choice(fixture['rides'])
        self.client.get('/api/v1/rides/' + ride['code'], headers=self.headers, name='ride detail')

    @task(3)
    def profile(self):
        self.client.get('/api/v1/me', headers=self.headers, name='profile')

    @task(2)
    def book_and_cancel(self):
        ride = random.choice(fixture['rides'])
        if ride['driver_id'] == self.account['user_id']:
            return
        with self.client.post('/api/v1/rides/' + ride['code'] + '/request', headers=self.headers,
                              json={'policy_ack': True}, name='booking request', catch_response=True) as res:
            if res.status_code == 409:
                res.success()  # Expected conflicts, including duplicate requests and full rides.
                return
            if res.status_code != 201:
                res.failure(f'Unexpected status {res.status_code}')
                return
            code = res.json()['code']
        self.client.post('/api/v1/bookings/' + code + '/cancel', headers=self.headers, json={}, name='booking cancel')

    @task(1)
    def post_ride(self):
        departure = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
        payload = {'city_pair': fixture['pair'], 'vehicle': self.account['vehicle'], 'seats_offered': 3,
                   'departure_at': departure, 'fare_inr': 0, 'pickup_point': 'Synthetic pickup',
                   'dropoff_point': 'Synthetic dropoff', 'policy_ack': True}
        with self.client.post('/api/v1/rides', headers=self.headers, json=payload, name='ride create',
                              catch_response=True) as res:
            if res.status_code != 201:
                res.failure(f'Unexpected status {res.status_code}')
            else:
                self.created_rides.append(res.json()['code'])
                self.created_rides = self.created_rides[-20:]

    @task(1)
    def update_ride(self):
        if self.created_rides:
            code = random.choice(self.created_rides)
            self.client.patch('/api/v1/rides/' + code, headers=self.headers, json={'notes': 'Synthetic update'},
                              name='ride update')
