import os
from ca_analyzer.parsers.hdfc_parser import HDFCParser
from ca_analyzer.parsers.icici_parser import ICICIParser
from ca_analyzer.parsers.sbi_parser import SBIParser

def test_hdfc_parser():
    path = "Bank Statements/Unprocessed/SANJAY JINDAL HDFC BANK STATEMENT FY 2024-25.xls"
    if os.path.exists(path):
        parser = HDFCParser(path)
        metadata = parser.extract_metadata()
        assert metadata["Person_Name"] == "SANJAY JINDAL"
        assert metadata["Bank_Name"] == "HDFC"
        
        df = parser.parse()
        assert df.shape[0] > 0
        assert "raw_date" in df.columns

def test_icici_parser():
    path = "Bank Statements/Unprocessed/SANJAY JINDAL ICICI BANK FY 2024-25.xls"
    if os.path.exists(path):
        parser = ICICIParser(path)
        metadata = parser.extract_metadata()
        assert metadata["Person_Name"] == "SANJAY JINDAL"
        assert metadata["Bank_Name"] == "ICICI"
        
        df = parser.parse()
        assert df.shape[0] > 0

def test_sbi_parser():
    path = "Bank Statements/Unprocessed/SANJAY JINDAL SBI 2024-25.xlsx"
    if os.path.exists(path):
        parser = SBIParser(path)
        metadata = parser.extract_metadata()
        assert "SANJAY JINDAL" in metadata["Person_Name"]
        assert metadata["Bank_Name"] == "SBI"
        
        df = parser.parse()
        assert df.shape[0] > 0
