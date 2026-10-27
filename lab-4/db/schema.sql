CREATE TABLE IF NOT EXISTS flights (
    carrier     TEXT        NOT NULL,
    flight_no   TEXT        NOT NULL,
    origin      VARCHAR(3)  NOT NULL,
    destination VARCHAR(3)  NOT NULL,
    departure   TIMESTAMP   NOT NULL,
    arrival     TIMESTAMP   NOT NULL,
    price       INTEGER     NOT NULL
);

-- выборка рейсов за дату
CREATE INDEX IF NOT EXISTS idx_flights_departure ON flights (departure);
