import financial_analytics as fa

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ->  {detail}" if detail else ""))


print("=" * 72)
print("CHECK GROUP D: ANALYTICS FUNCTIONS")
print("=" * 72)

y24 = fa.get_kpis_for_year(2024)
y23 = fa.get_kpis_for_year(2023)
y18 = fa.get_kpis_for_year(2018)

check("Revenue FY2024 = 391,035,000,000", y24 and y24["revenue"] == 391035000000.0,
      str(y24 and y24["revenue"]))
check("Revenue FY2023 = 383,285,000,000", y23 and y23["revenue"] == 383285000000.0,
      str(y23 and y23["revenue"]))
check("Revenue growth FY2018 = 15.86%", y18 and abs(y18["revenue_growth_pct"] - 15.86) < 0.01,
      str(y18 and y18["revenue_growth_pct"]))

cmp_ = fa.compare_years("revenue", 2023, 2024)
check("Compare revenue 2023 -> 2024: change = 7,750,000,000",
      cmp_ and cmp_["change"] == 7750000000.0, str(cmp_ and cmp_["change"]))
check("Compare revenue 2023 -> 2024: change = 2.02%",
      cmp_ and abs(cmp_["change_pct"] - 2.02) < 0.01, str(cmp_ and cmp_["change_pct"]))

best = fa.get_best_year("revenue")
check("Best revenue year = 2025", best and best["fiscal_year"] == 2025, str(best))

trend = fa.get_metric_trend("revenue")
check("Revenue trend has 9 years (2017-2025)", len(trend) == 9, f"{len(trend)} years")

old = fa.get_kpis_for_year(2016)
check("Revenue is empty (None) before 2017, not invented",
      old is None or old["revenue"] is None)

try:
    fa.get_metric_trend("revenue; DROP TABLE x")
    check("Unsafe metric name is rejected", False)
except ValueError:
    check("Unsafe metric name is rejected", True)

check("Unknown year returns None", fa.get_kpis_for_year(1900) is None)

summary = fa.get_summary()
check("Summary shows latest fiscal year 2025", summary and summary["fiscal_year"] == 2025,
      str(summary))

print()
print(f"{sum(RESULTS)} of {len(RESULTS)} checks passed")
print("ALL CHECKS PASSED." if all(RESULTS) else "Some checks FAILED. Send me this output.")
