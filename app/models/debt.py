"""Debts: money you owe (credit cards, loans) and money owed to you."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.database.db import get_connection

DEBT_TYPES = {"credit_card": "Credit Card", "loan": "Loan", "other": "Other"}
DEBT_TYPE_VALUES = {label: value for value, label in DEBT_TYPES.items()}


# --- Money I owe -------------------------------------------------------

@dataclass
class Debt:
    debt_id: int
    user_id: int
    creditor_name: str
    debt_type: str
    balance: float
    interest_rate: Optional[float]
    minimum_payment: Optional[float]
    due_date: Optional[str]
    notes: str
    created_at: str


def _row_to_debt(row) -> Debt:
    return Debt(
        debt_id=row["debt_id"], user_id=row["user_id"], creditor_name=row["creditor_name"],
        debt_type=row["debt_type"], balance=row["balance"], interest_rate=row["interest_rate"],
        minimum_payment=row["minimum_payment"], due_date=row["due_date"],
        notes=row["notes"] or "", created_at=row["created_at"],
    )


def list_debts() -> list[Debt]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM debts_i_owe ORDER BY creditor_name COLLATE NOCASE").fetchall()
    return [_row_to_debt(row) for row in rows]


def get_debt(debt_id: int) -> Optional[Debt]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM debts_i_owe WHERE debt_id = ?", (debt_id,)).fetchone()
    return _row_to_debt(row) if row else None


def total_debt_balance() -> float:
    return sum(debt.balance for debt in list_debts())


def get_debt_payoff_progress() -> list[dict]:
    """For each debt: how much has been paid so far vs. its current balance.
    percent_paid is based on payments recorded in this app, not a stored
    original balance (which this app doesn't separately track)."""
    conn = get_connection()
    results = []
    for debt in list_debts():
        total_paid_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM debt_payments "
            "WHERE debt_id = ? AND transaction_type = 'payment'", (debt.debt_id,)
        ).fetchone()
        total_paid = total_paid_row["total"]
        denominator = debt.balance + total_paid
        percent_paid = (total_paid / denominator * 100) if denominator > 0 else 0.0
        results.append({
            "creditor_name": debt.creditor_name, "balance": debt.balance,
            "total_paid": total_paid, "percent_paid": percent_paid,
        })
    return results


def create_debt(
    user_id: int, creditor_name: str, debt_type: str, balance: float,
    interest_rate: Optional[float], minimum_payment: Optional[float],
    due_date: Optional[str], notes: str,
) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO debts_i_owe (user_id, creditor_name, debt_type, balance, interest_rate,
            minimum_payment, due_date, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, creditor_name.strip(), debt_type, balance, interest_rate, minimum_payment,
         due_date, notes, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_debt(
    debt_id: int, creditor_name: str, debt_type: str, balance: float,
    interest_rate: Optional[float], minimum_payment: Optional[float],
    due_date: Optional[str], notes: str,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE debts_i_owe SET creditor_name=?, debt_type=?, balance=?, interest_rate=?,
            minimum_payment=?, due_date=?, notes=?
        WHERE debt_id=?
        """,
        (creditor_name.strip(), debt_type, balance, interest_rate, minimum_payment, due_date, notes, debt_id),
    )
    conn.commit()


def debt_has_linked_payments(debt_id: int) -> bool:
    """True if any Expense or Bill payment is linked to this debt (either
    paying it down or charging to it)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM expenses WHERE linked_debt_id = ? OR charged_debt_id = ? "
        "UNION SELECT 1 FROM bill_payments WHERE linked_debt_id = ? LIMIT 1",
        (debt_id, debt_id, debt_id),
    ).fetchone()
    return row is not None


def delete_debt(debt_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM debt_payments WHERE debt_id = ?", (debt_id,))
    conn.execute("DELETE FROM debts_i_owe WHERE debt_id = ?", (debt_id,))
    conn.commit()


def list_debt_payments(debt_id: int):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM debt_payments WHERE debt_id = ? ORDER BY payment_date DESC", (debt_id,)
    ).fetchall()


def record_debt_payment(
    debt_id: int, payment_date: str, amount: float,
    source_type: str = "manual", source_id: Optional[int] = None,
    transaction_type: str = "payment",
) -> int:
    """Records a payment or a charge against a debt, and adjusts its balance.

    transaction_type 'payment' REDUCES the balance (you paid some of it off).
    transaction_type 'charge' INCREASES the balance (you charged a new
    expense to it, e.g. a credit card purchase).

    source_type/source_id remember where this came from ('manual', 'bill',
    or 'expense'), so editing or deleting that bill/expense later can
    correctly reverse this exact entry.
    """
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO debt_payments (debt_id, payment_date, amount, source_type, source_id, transaction_type) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (debt_id, payment_date, amount, source_type, source_id, transaction_type),
    )
    if transaction_type == "charge":
        conn.execute("UPDATE debts_i_owe SET balance = balance + ? WHERE debt_id = ?", (amount, debt_id))
    else:
        conn.execute(
            "UPDATE debts_i_owe SET balance = MAX(0, balance - ?) WHERE debt_id = ?", (amount, debt_id)
        )
    conn.commit()
    return cursor.lastrowid


def unlink_debt_payment(source_type: str, source_id: int) -> None:
    """Reverses a payment/charge that was linked from a bill or expense
    (undoes its balance effect), then removes the record. Safe to call
    even if nothing is linked -- it simply does nothing.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT payment_id, debt_id, amount, transaction_type FROM debt_payments "
        "WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    ).fetchone()
    if row is None:
        return
    if row["transaction_type"] == "charge":
        # Reversing a charge means taking the amount back OFF the balance.
        conn.execute(
            "UPDATE debts_i_owe SET balance = MAX(0, balance - ?) WHERE debt_id = ?",
            (row["amount"], row["debt_id"]),
        )
    else:
        # Reversing a payment means giving the amount back.
        conn.execute(
            "UPDATE debts_i_owe SET balance = balance + ? WHERE debt_id = ?", (row["amount"], row["debt_id"])
        )
    conn.execute("DELETE FROM debt_payments WHERE payment_id = ?", (row["payment_id"],))
    conn.commit()


# --- Money owed to me ---------------------------------------------------

@dataclass
class Loan:
    loan_id: int
    user_id: int
    debtor_name: str
    amount: float
    date_lent: str
    due_date: Optional[str]
    notes: str
    created_at: str
    total_repaid: float

    @property
    def outstanding_balance(self) -> float:
        return max(0.0, self.amount - self.total_repaid)

    @property
    def status(self) -> str:
        if self.outstanding_balance <= 0:
            return "Paid"
        if self.total_repaid > 0:
            return "Partially Paid"
        return "Outstanding"


def _row_to_loan(row, total_repaid: float) -> Loan:
    return Loan(
        loan_id=row["loan_id"], user_id=row["user_id"], debtor_name=row["debtor_name"],
        amount=row["amount"], date_lent=row["date_lent"], due_date=row["due_date"],
        notes=row["notes"] or "", created_at=row["created_at"], total_repaid=total_repaid,
    )


def _total_repaid(conn, loan_id: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM loan_repayments WHERE loan_id = ?", (loan_id,)
    ).fetchone()
    return row["total"]


def list_loans() -> list[Loan]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM debts_owed_to_me ORDER BY debtor_name COLLATE NOCASE").fetchall()
    return [_row_to_loan(row, _total_repaid(conn, row["loan_id"])) for row in rows]


def get_loan(loan_id: int) -> Optional[Loan]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM debts_owed_to_me WHERE loan_id = ?", (loan_id,)).fetchone()
    return _row_to_loan(row, _total_repaid(conn, loan_id)) if row else None


def total_owed_to_me() -> float:
    return sum(loan.outstanding_balance for loan in list_loans())


def create_loan(user_id: int, debtor_name: str, amount: float, date_lent: str, due_date: Optional[str], notes: str) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO debts_owed_to_me (user_id, debtor_name, amount, date_lent, due_date, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, debtor_name.strip(), amount, date_lent, due_date, notes, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_loan(loan_id: int, debtor_name: str, amount: float, date_lent: str, due_date: Optional[str], notes: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE debts_owed_to_me SET debtor_name=?, amount=?, date_lent=?, due_date=?, notes=? WHERE loan_id=?",
        (debtor_name.strip(), amount, date_lent, due_date, notes, loan_id),
    )
    conn.commit()


def delete_loan(loan_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM loan_repayments WHERE loan_id = ?", (loan_id,))
    conn.execute("DELETE FROM debts_owed_to_me WHERE loan_id = ?", (loan_id,))
    conn.commit()


def list_loan_repayments(loan_id: int):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM loan_repayments WHERE loan_id = ? ORDER BY repayment_date DESC", (loan_id,)
    ).fetchall()


def record_loan_repayment(loan_id: int, repayment_date: str, amount: float) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO loan_repayments (loan_id, repayment_date, amount) VALUES (?, ?, ?)",
        (loan_id, repayment_date, amount),
    )
    conn.commit()
