# Finance Manager

A personal/household finance manager for Windows. 100% offline — no
internet, no cloud, no external database server. All your data lives in
one database file on your own computer.

© 2026 Ireneo John II Colet — john.colet.ca

**New here? See [GUIDE.md](GUIDE.md) for beginner-friendly, step-by-step instructions** —
including how to just install and use the app with no coding knowledge at all.

## What's included

- **Users & login**: Administrator/Regular User roles, 5-attempt lockout, 15-minute auto-logout
- **Expenses**: categories (editable), payment method, notes, receipt images, tax tags
- **Income**: salary/side/other, taxable flag, tax tags
- **Recurring bills**: due dates, frequency, paid/unpaid, in-app overdue/due-soon reminders, payment history
- **Debts**: money you owe (credit cards/loans, interest rate, minimum payment) and money owed to you, both with payment history
- **Tax tagging & yearly summary**: tag expenses/income, export a yearly summary to CSV for your accountant (the app only totals the numbers — it doesn't decide what's deductible)
- **Reports**: weekly/monthly/6-month/yearly summaries by category, export to PDF, Excel, and CSV
- **Dashboard**: income vs. expenses this month, spending-by-category chart, 6-month trend chart, upcoming bills, total debt, money owed to you
- **Backup & Restore** (Administrator only): manual backup to any folder, automatic backup on a schedule (keeps the last 10 copies by default), restore from any backup file, and a safeguarded "wipe database" option
- **Settings**: currency, date format, light/dark theme

## Where your data lives

- **Database file**: `%LOCALAPPDATA%\FinanceManager\FinanceManager.db`
  (typically `C:\Users\<YourName>\AppData\Local\FinanceManager\FinanceManager.db`)
- **Automatic backups folder**: `%LOCALAPPDATA%\FinanceManager\Backups\`
- During installation, you can choose a different folder for the database file.
  The app remembers your choice in a small file,
  `%LOCALAPPDATA%\FinanceManager\db_location.txt`.

Uninstalling the app does **not** delete this folder — your data and
backups are always safe across an uninstall, reinstall, or upgrade.

---

## (a) Installing on a new computer

1. Copy `installer/installer_output/FinanceManager-Setup.exe` to the new
   computer (USB drive, network share — no internet needed).
2. Run it. You do **not** need Python or anything else pre-installed.
3. During setup you'll be asked where to store the database file (the
   default is fine for most people).
4. The installer creates a desktop shortcut, a Start Menu entry, and an
   uninstaller.
5. On first launch, you'll be asked to create the Administrator account.

## (b) Moving your data from an old computer to a new one

1. On the **old** computer, log in as Administrator, go to
   **Backup & Restore**, and click **Back Up Now...**. Save the backup
   file to a USB drive (or any shared folder).
2. Install Finance Manager on the **new** computer as described above,
   and create a temporary Administrator account (you'll restore over it).
3. On the **new** computer, log in, go to **Backup & Restore**, click
   **Restore From Another File...**, and choose the backup file from
   the USB drive.
4. Confirm the warning. The app will log you out; log back in using the
   same username/password you had on the old computer — all your users,
   expenses, income, bills, debts, and settings are now restored.

## (c) Rebuilding the installer offline, from the build-kit

The `build-kit/` folder contains everything needed to rebuild the app
from scratch with **no internet connection**, even years from now:

- `python-installer/` — the exact Python installer used
- `inno-setup-installer/` — the Inno Setup installer used
- `wheels/` — every Python library this app needs, already downloaded
- `source/` — the complete source code, locked to exact versions in `requirements.txt`
- `build_offline.bat` — rebuilds everything automatically
- `checksums.sha256.txt` — SHA-256 fingerprints to verify nothing was corrupted

See `build-kit/README.txt` for full step-by-step instructions, including
how to verify the checksums and how to test the installer on a computer
with its network disconnected, to confirm it truly works offline.

---

## Running from source (for development)

```bash
cd finance-manager
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.main
```

## Rebuilding the .exe and installer yourself (with internet)

```bash
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean FinanceManager.spec
"C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer\FinanceManager.iss
```

The finished installer appears at `installer\installer_output\FinanceManager-Setup.exe`.
