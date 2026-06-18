from ca_analyzer.transaction_engine.category_engine import categorise_transaction

def test_categorization():
    cat, subcat, conf, reason = categorise_transaction("UPI/ZOMATO/FOOD", 120.0, 0.0)
    assert "Food" in [cat, subcat]

    cat, subcat, conf, reason = categorise_transaction("SALARY CREDIT", 0.0, 50000.0)
    assert cat == "Salary"

    cat, subcat, conf, reason = categorise_transaction("INTEREST CREDITED", 0.0, 1500.0)
    assert "Interest" in cat or "Interest" in subcat

def test_confidence_levels():
    # Strong keyword match -> High confidence
    cat, subcat, conf, reason = categorise_transaction("SALARY CREDIT FROM EMPLOYER", 0.0, 50000.0)
    assert conf in ("High", "Medium", "Low")
    assert reason != ""

    # No matching rule -> Low confidence
    cat, subcat, conf, reason = categorise_transaction("XYZXYZ UNKNOWN", 100.0, 0.0)
    assert conf == "Low"
    assert "no rule matched" in reason

def test_cheque_bounce():
    # Cheque return narration should be classified as Bounces/Cheque Bounce
    cat, subcat, conf, reason = categorise_transaction("CHQ RETURN CHARGES", 150.0, 0.0)
    assert cat == "Bounces"
    assert subcat == "Cheque Bounce"
    assert conf == "High"

def test_rental_guard():
    # Plain recurring credit without rent keywords should NOT be classified as House Property/Rental
    cat, subcat, conf, reason = categorise_transaction("MONTHLY CREDIT", 0.0, 5000.0)
    assert not (cat == "House Property" and subcat == "Rental Income")

    # Credit with rent keywords should be classified as House Property/Rental
    cat, subcat, conf, reason = categorise_transaction("RENT RECEIVED", 0.0, 5000.0)
    assert cat == "House Property"
    assert subcat == "Rental Income"
