

class TestBillingMetrics:

    def test_metrics_aggregation_schema(self, client):
        """GET /billing/metrics - Ensure dashboard calculations parse successfully into data structures."""
        r = client.get("/billing/metrics")
        assert r.status_code == 200
        data = r.json()
        
        metrics_fields = [
            "invoices_issued_today", 
            "invoices_paid_today", 
            "invoices_overdue", 
            "revenue_collected_mtd", 
            "anomalies_open", 
            "anomalies_critical", 
            "leakage_amount_flagged"
        ]
        for field in metrics_fields:
            assert field in data
            assert isinstance(data[field], (int, float))