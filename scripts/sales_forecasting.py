"""Run HealthCore sales forecast and write outputs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib.pyplot as plt
from src.sales_forecasting.pipeline import load_data, train_and_evaluate

result = train_and_evaluate(load_data())
Path("outputs").mkdir(exist_ok=True)
with open("outputs/sales_forecast_healthcore.json", "w", encoding="utf-8") as f:
    json.dump(result["metrics"], f, indent=2)
test = result["test"]
plt.figure(figsize=(12, 5))
plt.plot(test.month, test.revenue_usd, label="Actual revenue")
plt.plot(test.month, result["predictions"], label="Random Forest prediction")
plt.fill_between(test.month, result["lower"], result["upper"], alpha=.2, label="10–90% tree prediction range")
plt.axvline(test.month.iloc[0], color="gray", linestyle="--", label="Test begins")
plt.ylabel("Revenue (USD)"); plt.xlabel("Month"); plt.title("HealthCore revenue forecast: 2024–2025")
plt.legend(); plt.tight_layout(); plt.savefig("outputs/sales_forecast_healthcore.png", dpi=150)
print(json.dumps(result["metrics"], indent=2))
