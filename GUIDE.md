# Beginner's Guide to Finance Manager

This guide assumes you've never used Python or written code before. It
covers four things:

1. [Just using the app](#1-just-using-the-app-easiest) (easiest — most people stop here)
2. [Running the app from source code](#2-running-the-app-from-source-code)
3. [Installing Python](#3-installing-python)
4. [Building your own installer](#4-building-your-own-installer)

---

## 1. Just using the app (easiest)

If you only want to **use** Finance Manager, you don't need Python, a
code editor, or anything from this guide past this section.

1. Go to this repository's [Releases page](../../releases) or the
   `installer/installer_output/` folder, and download **`FinanceManager-Setup.exe`**.
2. Double-click it. Windows may show a blue "Windows protected your PC"
   screen because the app isn't signed by a paid certificate — click
   **More info**, then **Run anyway**. (This is normal for small
   independent apps; it does not mean the app is unsafe.)
3. Follow the setup wizard. Choose where to keep your database file (the
   default is fine), then finish.
4. The app opens. Since this is the first time, you'll be asked to
   create your **Administrator account** — pick a username and a
   password (at least 8 characters).
5. You're in! Start adding expenses, income, bills, and so on from the
   sidebar.

That's it — nothing below this line is required for everyday use.

---

## 2. Running the app from source code

Only do this if you want to see/change the code, or run it without
building an installer first.

### Step 1: Get the code

Either:
- Click the green **Code** button on this repository's GitHub page →
  **Download ZIP**, then extract it somewhere like `C:\FinanceManager`, or
- If you have Git installed: `git clone https://github.com/John-Colet/Windows-Finance-Manager-tool.git`

### Step 2: Open a terminal in that folder

In File Explorer, go into the `finance-manager` folder, click the
address bar, type `cmd`, and press Enter. A black command-prompt window
opens, already pointed at that folder.

### Step 3: Install Python

See [section 3](#3-installing-python) below if you don't have it yet.

### Step 4: Create a virtual environment and install the libraries

Copy-paste these one at a time into the command-prompt window:

```bash
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The second command downloads everything the app needs (this one step
does need internet). It can take a few minutes the first time.

### Step 5: Run the app

```bash
.venv\Scripts\python.exe -m app.main
```

The Finance Manager window should appear. To run it again later, you
only need Step 5 (Steps 3-4 are one-time setup).

---

## 3. Installing Python

1. Go to [python.org/downloads](https://www.python.org/downloads/) and
   download the Windows installer (any recent 3.11.x version works).
2. Run the installer. **Important:** on the first screen, check the box
   that says **"Add python.exe to PATH"** before clicking Install Now.
3. When it finishes, open a new command-prompt window and type `python --version`
   to confirm it printed a version number.

If you'd rather not download anything, this project's `build-kit\python-installer\`
folder (built locally on the original developer's machine, not included
in this public repository for size reasons) has the exact version used.

---

## 4. Building your own installer

This rebuilds `FinanceManager-Setup.exe` from the source code. You need:
- Python installed and the app running from source (sections 2-3 above)
- [Inno Setup](https://jrsoftware.org/isdl.php) installed (free, official tool
  that turns the app's files into one installer .exe)

Then, from the `finance-manager` folder, with your virtual environment
set up:

```bash
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean FinanceManager.spec
```

This creates `dist\FinanceManager\FinanceManager.exe` (the app itself,
as a folder of files). Then:

```bash
"C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer\FinanceManager.iss
```

(Adjust the path if Inno Setup installed somewhere else, such as
`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.)

Your new installer appears at:

```
installer\installer_output\FinanceManager-Setup.exe
```

### Rebuilding completely offline

If you have the full **build-kit** folder (ask the project owner for it,
or generate it yourself — see `build-kit/README.txt` in that folder),
you can rebuild with **no internet connection at all**, even if
python.org, PyPI, or jrsoftware.org are unreachable. Just run
`build-kit\build_offline.bat`. This public repository does not include
the build-kit itself (it's large and full of third-party installers),
but the full source code here is everything the build-kit's `source\`
folder contains.

---

## Where is my data?

No matter how you installed it, your data always lives at:

```
%LOCALAPPDATA%\FinanceManager\FinanceManager.db
```

Uninstalling the app, or rebuilding it from source, never touches this
file. Use the in-app **Backup & Restore** screen (as an Administrator)
to back up, restore, or move this data to another computer.
