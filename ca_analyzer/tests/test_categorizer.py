from ca_analyzer.transaction_engine.category_engine import categorise_transaction

def test_categorization():
    cat, subcat = categorise_transaction("UPI/ZOMATO/FOOD", 120.0, 0.0)
    assert "Food" in [cat, subcat]
    
    cat, subcat = categorise_transaction("SALARY CREDIT", 0.0, 50000.0)
    assert cat == "Salary"
    
    cat, subcat = categorise_transaction("INTEREST CREDITED", 0.0, 1500.0)
    assert "Interest" in cat or "Interest" in subcat
