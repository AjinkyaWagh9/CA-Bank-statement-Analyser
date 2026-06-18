# ca_analyzer/parsers/icici_parser.py

import re
import xlrd
import pandas as pd

from ca_analyzer.parsers.base_parser import BaseParser
from ca_analyzer.core.exceptions import ParserError
from ca_analyzer.core.utilities import parse_amount, parse_date


class ICICIParser(BaseParser):

    BANK_NAME = "ICICI"
    DEFAULT_IFSC = "ICIC0000046"

    _HEADER_KEYWORDS = {
        "s no.",
        "transaction date",
        "transaction remarks",
        "balance (inr )"
    }

    #######################################################################
    # METADATA EXTRACTION
    #######################################################################

    def extract_metadata(self) -> dict:
        book = xlrd.open_workbook(self.filepath)
        sheet = book.sheet_by_index(0)

        person_name = "N/A"
        account_number = "N/A"
        start_date = "N/A"
        end_date = "N/A"

        for r in range(min(50, sheet.nrows)):

            row = [
                str(sheet.cell_value(r, c)).strip()
                for c in range(sheet.ncols)
            ]

            row_text = " ".join(row)

            ###############################################################
            # ACCOUNT NUMBER + NAME
            ###############################################################

            if "Account Number" in row_text:

                for value in row:

                    if "-" in value:

                        parts = value.split("-", 1)

                        if len(parts) == 2:

                            account_number = (
                                parts[0]
                                .replace("(INR)", "")
                                .strip()
                            )

                            person_name = (
                                parts[1]
                                .strip()
                            )

                            break

            ###############################################################
            # DATE RANGE
            ###############################################################

            if "Transaction Date from" in row_text:

                dates = re.findall(
                    r"\d{2}/\d{2}/\d{4}",
                    row_text
                )

                if len(dates) >= 2:
                    start_date = dates[0]
                    end_date = dates[1]

        return {
            "Person_Name": person_name,
            "Bank_Name": self.BANK_NAME,
            "Account_Number": account_number,
            "IFSC": self.DEFAULT_IFSC,
            "Statement_Start": start_date,
            "Statement_End": end_date
        }

    #######################################################################
    # LOCATE HEADER ROW
    #######################################################################

    def _find_header_row(
            self,
            sheet
    ) -> int:

        for r in range(min(100, sheet.nrows)):

            row = [
                str(sheet.cell_value(r, c))
                .strip()
                .lower()
                for c in range(sheet.ncols)
            ]

            if self._HEADER_KEYWORDS.issubset(set(row)):
                return r

        raise ParserError(
            "ICICI transaction header row not found."
        )

    #######################################################################
    # EXTRACT TRANSACTIONS
    #######################################################################

    def extract_transactions(
            self
    ) -> pd.DataFrame:

        book = xlrd.open_workbook(
            self.filepath
        )

        sheet = book.sheet_by_index(0)

        header_row_idx = (
            self._find_header_row(sheet)
        )

        headers = [
            str(sheet.cell_value(
                header_row_idx,
                c
            )).strip()
            for c in range(sheet.ncols)
        ]

        rows = []
        seen_transaction = False

        ###################################################################
        # READ TRANSACTIONS
        ###################################################################

        for r in range(
                header_row_idx + 1,
                sheet.nrows
        ):

            row_vals = [
                sheet.cell_value(r, c)
                for c in range(sheet.ncols)
            ]

            # Some ICICI XLS exports repeat the header row immediately
            # after the first header, or start a duplicate data block
            # further down. Skip repeated headers before the first
            # transaction; stop when a header appears after transactions
            # have begun (that signals a second data block).
            row_lower = {
                str(v).strip().lower()
                for v in row_vals
            }
            if self._HEADER_KEYWORDS.issubset(row_lower):
                if seen_transaction:
                    break
                else:
                    continue

            if len(row_vals) < 8:
                continue

            ###############################################################
            # S.NO VALIDATION
            ###############################################################

            s_no = row_vals[0]

            if (
                s_no is None
                or str(s_no).strip() == ""
            ):
                continue

            try:
                float(s_no)
            except Exception:
                continue

            rows.append(row_vals)
            seen_transaction = True

        if len(rows) == 0:
            raise ParserError(
                "No transactions found in ICICI statement."
            )

        ###################################################################
        # CREATE DATAFRAME
        ###################################################################

        df = pd.DataFrame(
            rows,
            columns=headers
        )

        ###################################################################
        # REMOVE DUPLICATES
        ###################################################################

        dedupe_cols = [
            "Transaction Date",
            "Transaction Remarks",
            "Withdrawal Amount (INR )",
            "Deposit Amount (INR )",
            "Balance (INR )"
        ]

        available = [
            c
            for c in dedupe_cols
            if c in df.columns
        ]

        if available:

            before = len(df)

            # Normalize to strings for comparison so that xlrd cell-type
            # differences (float serial vs text) don't prevent dedup.
            dedup_key = df[available].astype(str).apply(
                lambda s: s.str.strip()
            )
            df = (
                df[~dedup_key.duplicated()]
                .reset_index(drop=True)
            )

            after = len(df)

            print(
                f"ICICI duplicates removed: "
                f"{before-after}"
            )

        ###################################################################
        # STANDARDIZE COLUMNS
        ###################################################################

        column_map = {
            "Transaction Date":
                "raw_date",

            "Transaction Remarks":
                "raw_narration",

            "Cheque Number":
                "raw_chq_ref",

            "Withdrawal Amount (INR )":
                "raw_debit",

            "Deposit Amount (INR )":
                "raw_credit",

            "Balance (INR )":
                "raw_balance"
        }

        canonical = pd.DataFrame()

        for source_col, target_col in (
                column_map.items()
        ):

            if source_col in df.columns:
                canonical[target_col] = (
                    df[source_col]
                )
            else:

                if (
                    "debit" in target_col
                    or "credit" in target_col
                    or "balance" in target_col
                ):
                    canonical[target_col] = 0.0
                else:
                    canonical[target_col] = ""

        ###################################################################
        # CLEAN DATA TYPES
        ###################################################################

        canonical["raw_date"] = (
            canonical["raw_date"]
            .apply(parse_date)
        )

        for col in [
            "raw_debit",
            "raw_credit",
            "raw_balance"
        ]:

            canonical[col] = (
                canonical[col]
                .apply(parse_amount)
                .fillna(0.0)
            )

        ###################################################################
        # DEBUG RECONCILIATION
        ###################################################################

        print("=" * 60)
        print("ICICI RECONCILIATION")
        print(
            "Transactions:",
            len(canonical)
        )
        print(
            "Debit:",
            canonical["raw_debit"].sum()
        )
        print(
            "Credit:",
            canonical["raw_credit"].sum()
        )

        if len(canonical):

            print(
                "Closing:",
                canonical.iloc[-1][
                    "raw_balance"
                ]
            )

        print("=" * 60)

        return canonical