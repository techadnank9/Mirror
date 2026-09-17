import unittest
from datetime import date

from mirror import normalize
from mirror.dates import month_range, parse_date
from mirror.demo import generate
from mirror.weather import condition, precipitation, pressure, score_pool, temperature

ASOF = date(2026, 9, 17)


class DatesTest(unittest.TestCase):
    def test_parse_formats(self):
        self.assertEqual(parse_date("2026-03-05"), date(2026, 3, 5))
        self.assertEqual(parse_date("2026-03"), date(2026, 3, 1))
        self.assertEqual(parse_date("2026-03-05T10:00:00Z"), date(2026, 3, 5))
        self.assertEqual(parse_date(1_700_000_000), date(2023, 11, 14))
        self.assertEqual(parse_date("Mar 2026"), date(2026, 3, 1))
        self.assertIsNone(parse_date("nope"))

    def test_month_range(self):
        self.assertEqual(month_range(ASOF, 3), ["2026-07", "2026-08", "2026-09"])


class NormalizeTest(unittest.TestCase):
    def test_traffic_from_list(self):
        raw = {"data": {"history": [{"date": "2026-07-01", "visits": "12k"}, {"date": "2026-08-01", "visits": 15000}]}}
        self.assertEqual(normalize.extract_traffic(raw), [{"month": "2026-07", "visits": 12000.0}, {"month": "2026-08", "visits": 15000.0}])

    def test_traffic_from_month_dict(self):
        raw = {"visits_by_month": {"2026-06": 100, "2026-07": 120, "2026-08": 150}}
        self.assertEqual([t["visits"] for t in normalize.extract_traffic(raw)], [100.0, 120.0, 150.0])

    def test_funding_flat_fields(self):
        raw = {"company": {"last_funding_date": "2026-02-10", "last_funding_type": "Series A", "total_funding": 12000000}}
        f = normalize.extract_funding(raw)
        self.assertEqual(f[0]["round"], "Series A")
        self.assertEqual(f[0]["amount_usd"], 12000000.0)

    def test_people_and_news(self):
        raw = {"results": [{"full_name": "A B", "job_title": "VP Sales", "job_start_date": "2026-08-01"}]}
        p = normalize.extract_people(raw)[0]
        self.assertEqual(p["function"], "sales")
        n = normalize.extract_news({"articles": [{"title": "Acme lays off 20% of staff", "published_at": "2026-08-02"}]})
        self.assertEqual(n[0]["kind"], "layoff")

    def test_company_domain_cleanup(self):
        c = normalize.extract_company({"name": "Acme", "website": "https://www.acme.io/about", "industry": "Software"})
        self.assertEqual(c["domain"], "acme.io")


class WeatherTest(unittest.TestCase):
    def test_temperature_rising(self):
        traffic = [{"month": m, "visits": 1000 * (1.15 ** i)} for i, m in enumerate(month_range(ASOF, 8))]
        t, why = temperature(traffic, "2026-09")
        self.assertGreater(t, 0.5)
        self.assertIn("+", why)

    def test_temperature_needs_history(self):
        self.assertEqual(temperature([], "2026-09")[0], None)

    def test_pressure_layoffs_dominate(self):
        news = [{"date": "2026-08-20", "kind": "layoff", "title": "X lays off 30%"}]
        jobs = [{"date": "2026-09-01"}] * 10
        p, why = pressure(jobs, news, "2026-09")
        self.assertEqual(p, -0.8)
        self.assertIn("layoffs", why)

    def test_precipitation_gap(self):
        self.assertEqual(precipitation([{"date": "2026-06-01", "round": "Seed"}], "2026-09")[0], 1.0)
        self.assertEqual(precipitation([{"date": "2023-01-01", "round": "Seed"}], "2026-09")[0], 0.0)
        self.assertEqual(precipitation([], "2026-09")[0], 0.2)

    def test_conditions(self):
        self.assertEqual(condition(0.5, 0.3, 1.0, 0.0, 0.5, True), "sunny")
        self.assertEqual(condition(-0.6, -0.5, 0.0, 0.0, 0.5, True), "storm")
        self.assertEqual(condition(0.0, 0.0, 0.5, 0.8, 0.5, True), "front")
        self.assertEqual(condition(None, None, 0.2, 0.0, 0.05, False), "fog")
        self.assertEqual(condition(0.05, 0.0, 0.5, 0.0, 0.5, True), "cloudy")
        # hiring noise alone must not make a storm
        self.assertEqual(condition(0.0, -0.5, 0.5, 0.0, 0.5, True), "cloudy")

    def test_demo_covers_every_condition(self):
        scored = score_pool(generate(ASOF, seed=7), ASOF)
        conds = {s["current"]["condition"] for s in scored}
        self.assertEqual(conds, {"sunny", "cloudy", "storm", "front", "fog"})
        self.assertTrue(all(len(s["snapshots"]) == 12 for s in scored))


if __name__ == "__main__":
    unittest.main()
