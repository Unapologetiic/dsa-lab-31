"""Составление маршрутов. Не обращается ни к сети, ни к базе данных."""
import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_LAYOVER = timedelta(hours=1)
MAX_LAYOVER = timedelta(hours=6)
TOP_N = 20


@dataclass(frozen=True)
class Flight:
    carrier: str
    flight_no: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    price: int


def _can_connect(prev: Flight, nxt: Flight) -> bool:
    return MIN_LAYOVER <= nxt.departure - prev.arrival <= MAX_LAYOVER


def build_routes(flights: list[Flight], origin: str, destination: str) -> list[tuple[Flight, ...]]:
    """Прямые маршруты и маршруты с 1-2 пересадками; 20 самых дешёвых."""
    by_origin = defaultdict(list)
    by_pair = defaultdict(list)
    for f in flights:
        by_origin[f.origin].append(f)
        by_pair[(f.origin, f.destination)].append(f)

    routes = []
    for f1 in by_origin[origin]:
        a = f1.destination
        if a == destination:                      # прямой рейс
            routes.append((f1,))
            continue
        if a == origin:
            continue
        for f2 in by_pair[(a, destination)]:      # одна пересадка
            if _can_connect(f1, f2):
                routes.append((f1, f2))
        for f2 in by_origin[a]:                   # две пересадки
            b = f2.destination
            if b in (origin, destination, a) or not _can_connect(f1, f2):
                continue
            for f3 in by_pair[(b, destination)]:
                if _can_connect(f2, f3):
                    routes.append((f1, f2, f3))

    return heapq.nsmallest(TOP_N, routes, key=lambda r: sum(f.price for f in r))


def route_to_dict(route: tuple[Flight, ...]) -> dict:
    return {
        "price": sum(f.price for f in route),
        "flights": [
            {
                "carrier": f.carrier,
                "flight_no": f.flight_no,
                "origin": f.origin,
                "destination": f.destination,
                "departure": f.departure.isoformat(),
                "arrival": f.arrival.isoformat(),
                "price": f.price,
            }
            for f in route
        ],
    }
