"""Export a period summary to CSV, Excel, or PDF."""

from __future__ import annotations

import csv


def export_summary_to_csv(summary: dict, file_path: str) -> None:
    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([f"Summary: {summary['start_date']} to {summary['end_date']}"])
        writer.writerow([])
        writer.writerow(["Total Income", f"{summary['total_income']:.2f}"])
        writer.writerow(["Total Expenses", f"{summary['total_expenses']:.2f}"])
        writer.writerow(["Net Savings", f"{summary['net_savings']:.2f}"])
        writer.writerow([])
        writer.writerow(["Expenses by Category"])
        writer.writerow(["Category", "Total"])
        for row in summary["expenses_by_category"]:
            writer.writerow([row["category_name"], f"{row['total']:.2f}"])


def export_summary_to_excel(summary: dict, file_path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Summary"

    bold = Font(bold=True)

    sheet.append([f"Summary: {summary['start_date']} to {summary['end_date']}"])
    sheet["A1"].font = bold
    sheet.append([])
    sheet.append(["Total Income", summary["total_income"]])
    sheet.append(["Total Expenses", summary["total_expenses"]])
    sheet.append(["Net Savings", summary["net_savings"]])
    sheet.append([])
    sheet.append(["Expenses by Category"])
    sheet["A7"].font = bold
    sheet.append(["Category", "Total"])
    for row in summary["expenses_by_category"]:
        sheet.append([row["category_name"], row["total"]])

    for column_letter in ("A", "B"):
        sheet.column_dimensions[column_letter].width = 24

    workbook.save(file_path)


def export_summary_to_pdf(summary: dict, file_path: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    elements = [
        Paragraph("Finance Manager - Summary Report", styles["Title"]),
        Paragraph(f"Period: {summary['start_date']} to {summary['end_date']}", styles["Normal"]),
        Spacer(1, 16),
        Paragraph(f"Total Income: {summary['total_income']:.2f}", styles["Normal"]),
        Paragraph(f"Total Expenses: {summary['total_expenses']:.2f}", styles["Normal"]),
        Paragraph(f"Net Savings: {summary['net_savings']:.2f}", styles["Normal"]),
        Spacer(1, 16),
        Paragraph("Expenses by Category", styles["Heading2"]),
    ]

    table_data = [["Category", "Total"]]
    for row in summary["expenses_by_category"]:
        table_data.append([row["category_name"], f"{row['total']:.2f}"])

    table = Table(table_data, colWidths=[260, 120])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ])
    )
    elements.append(table)

    doc.build(elements)
