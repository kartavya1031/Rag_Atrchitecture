"""Comprehensive API functionality test script.

Run manually:  python tests/test_api_manual.py
NOT collected by pytest (guarded by ``if __name__``).
"""
import json
import sys
import requests

BASE = "http://127.0.0.1:8001"
results = []


def _run_test(name, fn):
    try:
        passed, detail = fn()
        status = "PASS" if passed else "FAIL"
        results.append({"name": name, "status": status, "detail": detail})
        print(f"[{status}] {name}: {detail}")
    except Exception as e:
        results.append({"name": name, "status": "ERROR", "detail": str(e)})
        print(f"[ERROR] {name}: {e}")


# ── Test 1: Dashboard / List Documents (empty) ──
def _manual_test_list_docs_initial():
    r = requests.get(f"{BASE}/knowledge-base/documents")
    assert r.status_code == 200
    return True, f"Status 200, {len(r.json())} docs"


# ── Test 2: Upload text document to KB ──
def _manual_test_upload_txt():
    content = (
        "Standard Operating Procedure: Daily Bank Reconciliation\n\n"
        "Step 1: Download the bank statement for the previous business day.\n"
        "Step 2: Import the statement into the reconciliation system.\n"
        "Step 3: Run automatic matching against the general ledger.\n"
        "Step 4: Review any unmatched transactions in the exception queue.\n"
        "Step 5: Investigate and resolve each exception item.\n"
        "Step 6: Approve or reject exceptions with documented reasons.\n"
        "Step 7: Generate the reconciliation report and archive.\n"
    )
    files = {"file": ("daily_reconciliation_sop.txt", content.encode(), "text/plain")}
    r = requests.post(f"{BASE}/knowledge-base/upload", files=files)
    assert r.status_code == 200
    data = r.json()
    return data["status"] == "ingested", f"Ingested {data['chunk_count']} chunks, hash={data['content_hash']}"


# ── Test 3: Upload duplicate document ──
def _manual_test_upload_duplicate():
    content = (
        "Standard Operating Procedure: Daily Bank Reconciliation\n\n"
        "Step 1: Download the bank statement for the previous business day.\n"
        "Step 2: Import the statement into the reconciliation system.\n"
        "Step 3: Run automatic matching against the general ledger.\n"
        "Step 4: Review any unmatched transactions in the exception queue.\n"
        "Step 5: Investigate and resolve each exception item.\n"
        "Step 6: Approve or reject exceptions with documented reasons.\n"
        "Step 7: Generate the reconciliation report and archive.\n"
    )
    files = {"file": ("daily_reconciliation_sop.txt", content.encode(), "text/plain")}
    r = requests.post(f"{BASE}/knowledge-base/upload", files=files)
    assert r.status_code == 200
    return r.json()["status"] == "already_exists", f"Correctly detected duplicate"


# ── Test 4: List Documents after upload ──
def _manual_test_list_docs_after():
    r = requests.get(f"{BASE}/knowledge-base/documents")
    assert r.status_code == 200
    docs = r.json()
    return len(docs) >= 1, f"Found {len(docs)} document(s)"


# ── Test 5: Search knowledge base ──
def _manual_test_search_kb():
    r = requests.get(f"{BASE}/knowledge-base/search", params={"q": "reconciliation steps", "n": 5})
    assert r.status_code == 200
    hits = r.json()
    if hits:
        top = hits[0]
        return True, f"{len(hits)} results, top similarity={top['similarity']}"
    return False, "No results"


# ── Test 6: Reconciliation with bank + ledger CSVs ──
def _manual_test_reconciliation():
    bank_path = r"d:\personal_project\bank-reconciliation-agent\data\test_samples\bank_statement.csv"
    ledger_path = r"d:\personal_project\bank-reconciliation-agent\data\test_samples\ledger.csv"
    
    with open(bank_path, "rb") as bf, open(ledger_path, "rb") as lf:
        files = {
            "file": ("bank_statement.csv", bf, "text/csv"),
            "ledger_file": ("ledger.csv", lf, "text/csv"),
        }
        data = {"bank_name": "Generic"}
        r = requests.post(f"{BASE}/reconcile", files=files, data=data)
    
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    
    # Fetch report
    rr = requests.get(f"{BASE}/reconcile/{run_id}/report")
    assert rr.status_code == 200
    report = rr.json()
    
    detail = (
        f"run_id={run_id[:8]}..., "
        f"matched={report['matched_count']}, "
        f"unmatched_ledger={report['unmatched_ledger_count']}, "
        f"unmatched_bank={report['unmatched_bank_count']}"
    )
    return True, detail


# ── Test 7: Reconciliation status ──
def _manual_test_reconciliation_status():
    # Run a reconciliation first
    bank_path = r"d:\personal_project\bank-reconciliation-agent\data\test_samples\bank_statement.csv"
    with open(bank_path, "rb") as bf:
        files = {"file": ("bank_statement.csv", bf, "text/csv")}
        data = {"bank_name": "Chase"}
        r = requests.post(f"{BASE}/reconcile", files=files, data=data)
    
    run_id = r.json()["run_id"]
    sr = requests.get(f"{BASE}/reconcile/{run_id}/status")
    assert sr.status_code == 200
    status_data = sr.json()
    return status_data["status"] in ("completed", "running", "failed"), f"Status: {status_data['status']}"


# ── Test 8: Unsupported file upload ──
def _manual_test_unsupported_file():
    files = {"file": ("bad.exe", b"fake", "application/octet-stream")}
    r = requests.post(f"{BASE}/knowledge-base/upload", files=files)
    return r.status_code == 400, f"Correctly rejected with status {r.status_code}"


# ── Test 9: 404 for non-existent run ──
def _manual_test_nonexistent_run():
    r = requests.get(f"{BASE}/reconcile/fake-id/status")
    return r.status_code == 404, f"Correctly returned 404"


# ── Test 10: Delete Document ──
def _manual_test_delete_doc():
    r = requests.get(f"{BASE}/knowledge-base/documents")
    docs = r.json()
    if not docs:
        return True, "No docs to delete"
    doc = docs[0]
    dr = requests.delete(
        f"{BASE}/knowledge-base/documents/{doc['filename']}",
        params={"content_hash": doc["content_hash"]}
    )
    assert dr.status_code == 200
    return dr.json()["deleted_chunks"] > 0, f"Deleted {dr.json()['deleted_chunks']} chunks of {doc['filename']}"


# ── Test 11: Search with filename filter ──
def _manual_test_search_with_filter():
    # Upload a doc first
    files = {"file": ("filter_test.txt", b"Bank reconciliation policy document for testing search filters", "text/plain")}
    requests.post(f"{BASE}/knowledge-base/upload", files=files)
    
    r = requests.get(f"{BASE}/knowledge-base/search", params={"q": "policy", "n": 5, "filename": "filter_test.txt"})
    assert r.status_code == 200
    hits = r.json()
    return len(hits) > 0, f"{len(hits)} results with filename filter"


# ── Test 12: Reconciliation with bank-only (no ledger) ──
def _manual_test_bank_only_reconciliation():
    bank_path = r"d:\personal_project\bank-reconciliation-agent\data\test_samples\bank_statement.csv"
    with open(bank_path, "rb") as bf:
        files = {"file": ("bank_statement.csv", bf, "text/csv")}
        data = {"bank_name": "Generic"}
        r = requests.post(f"{BASE}/reconcile", files=files, data=data)
    
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    rr = requests.get(f"{BASE}/reconcile/{run_id}/report")
    report = rr.json()
    return True, f"Bank-only: matched={report['matched_count']}, unmatched_bank={report['unmatched_bank_count']}"


def main():
    _run_test("1. List Documents (initial)", _manual_test_list_docs_initial)
    _run_test("2. Upload Text Document", _manual_test_upload_txt)
    _run_test("3. Upload Duplicate Detection", _manual_test_upload_duplicate)
    _run_test("4. List Documents (after upload)", _manual_test_list_docs_after)
    _run_test("5. Knowledge Base Search", _manual_test_search_kb)
    _run_test("6. Reconciliation (bank + ledger)", _manual_test_reconciliation)
    _run_test("7. Reconciliation Status Check", _manual_test_reconciliation_status)
    _run_test("8. Reject Unsupported File Type", _manual_test_unsupported_file)
    _run_test("9. Non-existent Run Returns 404", _manual_test_nonexistent_run)
    _run_test("10. Delete Document", _manual_test_delete_doc)
    _run_test("11. Search with Filename Filter", _manual_test_search_with_filter)
    _run_test("12. Reconciliation (bank only, no ledger)", _manual_test_bank_only_reconciliation)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print("=" * 60)

    for r in results:
        icon = "✓" if r["status"] == "PASS" else ("✗" if r["status"] == "FAIL" else "!")
        print(f"  {icon} {r['name']}: {r['detail']}")

    if failed + errors > 0:
        print("\nSome tests failed! Review details above.")
        sys.exit(1)
    else:
        print("\nAll tests passed!")


if __name__ == "__main__":
    main()
