"""Нагрузочный скрипт (asyncio + httpx.AsyncClient).

Замкнутый режим:  python load.py closed --clients 10
Открытый режим:   python load.py open --rate 5
Общие параметры:  --duration 60 --warmup 10 --timeout 30 --url http://localhost:8000
Перцентили считаются методом ближайшего ранга.
"""
import argparse
import asyncio
import datetime as dt
import math
import random
import time

import httpx

START_DATE = dt.date(2026, 11, 1)   # то же значение в db/generate.py
DAYS = 120
AIRPORTS = [
    "SVO", "DME", "VKO", "LED", "AER", "KZN", "OVB", "SVX", "KRR", "ROV",
    "UFA", "KGD", "GOJ", "MRV", "KUF", "CEK", "IKT", "KJA", "VVO", "KHV",
    "MMK", "ARH", "PEE", "TJM", "OMS", "TOF", "UUD", "YKS", "VOG", "VOZ",
]


def percentile(sorted_values, p):
    return sorted_values[math.ceil(p / 100 * len(sorted_values)) - 1]


class Stats:
    def __init__(self):
        self.latencies = []   # мс
        self.errors = 0

    def add(self, latency_ms, ok):
        self.latencies.append(latency_ms)
        if not ok:
            self.errors += 1

    def report(self, title, duration):
        n = len(self.latencies)
        print(f"--- {title} ---")
        if n == 0:
            print("нет данных")
            return
        lat = sorted(self.latencies)
        print(f"запросов:        {n}")
        print(f"запросов в с:    {n / duration:.2f}")
        print(f"p50, мс:         {percentile(lat, 50):.1f}")
        print(f"p95, мс:         {percentile(lat, 95):.1f}")
        print(f"p99, мс:         {percentile(lat, 99):.1f}")
        print(f"макс., мс:       {lat[-1]:.1f}")
        print(f"ошибки, %:       {self.errors / n * 100:.2f}")


async def run(args):
    rnd = random.Random(42)

    def next_params():
        origin, destination = rnd.sample(AIRPORTS, 2)
        date = START_DATE + dt.timedelta(days=rnd.randrange(DAYS))
        return {"origin": origin, "destination": destination, "date": date.isoformat()}

    start = time.monotonic()
    warm_end = start + args.warmup
    end = warm_end + args.duration
    search, health = Stats(), Stats()

    limits = httpx.Limits(max_connections=None, max_keepalive_connections=None)
    async with httpx.AsyncClient(base_url=args.url, timeout=args.timeout, limits=limits) as client:

        async def request(path, params, stats):
            t = time.monotonic()
            try:
                r = await client.get(path, params=params)
                ok = r.status_code < 400          # 4xx и 5xx - ошибки
            except httpx.HTTPError:
                ok = False                        # в том числе тайм-аут клиента
            if t >= warm_end:                     # прогрев не учитываем
                stats.add((time.monotonic() - t) * 1000, ok)

        async def closed_worker():
            while time.monotonic() < end:
                await request("/search", next_params(), search)

        async def open_load():
            tasks = []
            next_t = time.monotonic()
            while next_t < end:
                delay = next_t - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                tasks.append(asyncio.create_task(request("/search", next_params(), search)))
                next_t += random.expovariate(args.rate)   # экспоненциальные интервалы
            await asyncio.gather(*tasks)

        async def poll_health():
            tasks = []
            next_t = time.monotonic()
            while next_t < end:
                delay = next_t - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                tasks.append(asyncio.create_task(request("/health", None, health)))
                next_t += 0.1                              # каждые 100 мс
            await asyncio.gather(*tasks)

        if args.mode == "closed":
            load = asyncio.gather(*(closed_worker() for _ in range(args.clients)))
        else:
            load = open_load()
        await asyncio.gather(load, poll_health())

    search.report("search", args.duration)
    health.report("health", args.duration)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["closed", "open"])
    p.add_argument("--clients", type=int, default=1, help="C для замкнутого режима")
    p.add_argument("--rate", type=float, default=5, help="запросов в секунду для открытого режима")
    p.add_argument("--duration", type=float, default=60)
    p.add_argument("--warmup", type=float, default=10)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--url", default="http://localhost:8000")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
