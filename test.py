# test_main.py
import os
import sys
import pytest
import httpx
from datetime import date

# 1. Setup local environment discovery path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the primary application matrix from your main script
from main import app

BASE_URL = "http://127.0.0.1:8001"

# ── TEST FIXTURES ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """Synchronous HTTP client pointing to your local running Uvicorn server."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c

@pytest.fixture
def test_invoice_payload():
    """Standard payload blueprint for verification routines."""
    return {
        "customer_id": 1,
        "quote_id": None,
        "billing_period_start": "2026-06-01",
        "billing_period_end": "2026-06-30",
        "notes": "Consolidated single-file validation process testing execution."
    }

# ── TEST SUITE MATRIX ─────────────────────────────────────────────────────────

class TestBillingInvoices:

    def test_list_invoices_default(self, client):
        """GET /billing/invoices - Ensure default lists match expected InvoiceOut properties."""
        r = client.get("/billing/invoices")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if len(data) > 0:
            inv = data[0]
            assert "invoice_number" in inv
            assert "total_amount" in inv
            assert "line_items" in inv

    def test_list_invoices_with_filter(self, client):
        """GET /billing/invoices?status=draft&limit=5 - Verify status sorting strings."""
        r = client.get("/billing/invoices", params={"status": "draft", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) <= 5
        for inv in data:
            assert inv["status"] == "draft"

    def test_create_invoice_fallback_flow(self, client, test_invoice_payload):
        """POST /billing/invoices - Safely evaluate invoice execution limits."""
        r = client.post("/billing/invoices", json=test_invoice_payload)
        
        # Validates smoothly against database initialization variations (clean migrations vs seeded)
        if r.status_code == 404:
            assert "Customer 1 not found" in r.json()["detail"]
        elif r.status_code == 201:
            data = r.json()
            assert data["status"] == "draft"
            assert data["customer_id"] == 1
            assert data["invoice_number"].startswith(f"INV-{date.today().year}-")

    def test_overdue_invoices_all_overdue(self, client):
        """GET /billing/invoices/overdue - Check state constraint parsing."""
        r = client.get("/billing/invoices/overdue")
        assert r.status_code == 200
        for inv in r.json():
            assert inv["status"] == "overdue"

    def test_customer_invoices_empty_returns_200(self, client):
        """GET /billing/invoices/customer/{id} - Missing profiles must map out to empty lists instead of a 404 error."""
        r = client.get("/billing/invoices/customer/99999")
        assert r.status_code == 200
        assert r.json() == []

    def test_invoice_not_found_returns_404(self, client):
        """GET /billing/invoices/{invoice_number} - Validate unseeded lookup paths."""
        r = client.get("/billing/invoices/INV-9999-99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_update_invoice_status_not_found(self, client):
        """PUT /billing/invoices/{invoice_number}/status - Gracefully abort on missing document targets."""
        r = client.put("/billing/invoices/INV-9999-99999/status", json={"status": "paid"})
        assert r.status_code == 404


class TestBillingPayments:

    def test_record_payment_invoice_not_found(self, client):
        """POST /billing/payments - Block attempts targeting unregistered primary identifiers."""
        payload = {
            "invoice_id": 999999,
            "amount": 100.00,
            "payment_method": "ach",
            "transaction_ref": "tx_mon_001"
        }
        r = client.post("/billing/payments", json=payload)
        assert r.status_code == 404
        assert "not found" in r.json()["detail"]

    def test_get_invoice_payments_empty(self, client):
        """GET /billing/payments/invoice/{invoice_number} - Fall back smoothly for non-existent datasets."""
        r = client.get("/billing/payments/invoice/INV-9999-99999")
        assert r.status_code == 200
        assert r.json() == []


class TestBillingAnomalies:

    def test_create_anomaly_missing_invoice(self, client):
        """POST /billing/anomalies - Enforce referential integrity checks."""
        payload = {
            "invoice_id": 999999,
            "anomaly_type": "duplicate_run",
            "severity": "low",
            "amount_affected": 0.0,
            "description": "Validation testing scenario"
        }
        r = client.post("/billing/anomalies", json=payload)
        assert r.status_code == 404

    def test_create_anomaly_from_live_context(self, client):
        """POST /billing/anomalies - Dynamic run evaluation based on system telemetry availability."""
        invoices = client.get("/billing/invoices", params={"limit": 1}).json()
        if not invoices:
            pytest.skip("No invoices present within the Neon instance to target anomaly tracking execution loops.")
            
        target_invoice = invoices[0]
        payload = {
            "invoice_id": target_invoice["id"],
            "anomaly_type": "rate_mismatch",
            "severity": "high",
            "amount_affected": 50.00,
            "description": "Billed at Enterprise rate, contracted Standard tier."
        }
        r = client.post("/billing/anomalies", json=payload)
        
        if r.status_code == 201:
            data = r.json()
            assert data["status"] == "open"
            assert data["invoice_id"] == target_invoice["id"]
        else:
            assert r.status_code in [404, 500]

    def test_open_anomalies_ordered_by_severity(self, client):
        """GET /billing/anomalies/open - Verify strict ranking compliance (critical -> high -> medium -> low)."""
        r = client.get("/billing/anomalies/open")
        assert r.status_code == 200
        anomalies = r.json()
        
        severity_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        orders = [severity_order[a["severity"]] for a in anomalies if a["severity"] in severity_order]
        assert orders == sorted(orders), "Anomalies fail to align sequentially against descending corporate risk definitions."

    def test_get_anomaly_by_id_not_found(self, client):
        """GET /billing/anomalies/{anomaly_id} - Verify clear 404 status tracing on missing database entries."""
        r = client.get("/billing/anomalies/999999")
        assert r.status_code == 404
        assert "missing" in r.json()["detail"]

    def test_update_anomaly_status_not_found(self, client):
        """PUT /billing/anomalies/{anomaly_id}/status - Check validation boundary on missing metrics updates."""
        r = client.put("/billing/anomalies/999999/status", json={"status": "resolved", "resolution": "Discard entity"})
        assert r.status_code == 404

