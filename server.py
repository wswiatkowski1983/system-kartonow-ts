import os
import sqlite3
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "kartony.db"


def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    cur = conn.cursor()

    # Tabela mapowania: (grupa + modelkolor) -> karton
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kartony (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupa TEXT NOT NULL,
            modelkolor TEXT NOT NULL,
            karton TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Unikalność jako indeks (działa też, gdy tabela już była)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_kartony_grupa_model
        ON kartony(grupa, modelkolor)
    """)

    # Historia skanów (każde kliknięcie "Skanuj" zapisuje się tutaj)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skany (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupa TEXT NOT NULL,
            modelkolor TEXT NOT NULL,
            karton TEXT NOT NULL,
            status TEXT NOT NULL, -- NOWY / ZNALEZIONO
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


def next_karton_for_group(cur, grupa: str) -> str:
    """
    Nadaje kolejny karton dla danej grupy.
    Format: GRUPA-001, GRUPA-002, ...
    """
    cur.execute(
        "SELECT karton FROM kartony WHERE grupa = ? ORDER BY id DESC LIMIT 1",
        (grupa,)
    )
    row = cur.fetchone()

    if not row:
        return f"{grupa}-001"

    last = row["karton"]  # np. ZAK-017
    try:
        num = int(str(last).split("-")[-1])
    except Exception:
        num = 0

    return f"{grupa}-{num + 1:03d}"


def save_scan(grupa: str, model: str, karton: str, status: str) -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO skany (grupa, modelkolor, karton, status) VALUES (?, ?, ?, ?)",
        (grupa, model, karton, status)
    )
    conn.commit()
    conn.close()


@app.get("/")
def home():
    return """
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>System Kartonów TS</title>
      </head>
      <body style="font-family: Arial; text-align:center; margin-top:60px;">
        <h1>System Kartonów TS</h1>

        <form method="POST" action="/scan">
          <div style="margin:16px;">
            <div style="margin-bottom:6px;">Grupa:</div>
            <input name="grupa" style="width:280px; height:32px; font-size:18px;" />
          </div>

          <div style="margin:16px;">
            <div style="margin-bottom:6px;">ModelKolor:</div>
            <input name="modelkolor" style="width:280px; height:32px; font-size:18px;" />
          </div>

          <button type="submit" style="width:170px; height:48px; font-size:18px;">Skanuj</button>
        </form>

        <div style="margin-top:26px;">
          <a href="/recent" style="display:inline-block; padding:12px 18px; border:1px solid #333; text-decoration:none; font-size:18px; border-radius:6px;">
            Pokaż ostatnie 20 skanów
          </a>
        </div>

      </body>
    </html>
    """


@app.route("/scan", methods=["POST", "GET"])
def scan():
    if request.method == "GET":
        return home()

    grupa = (request.form.get("grupa") or "").strip().upper()
    model = (request.form.get("modelkolor") or "").strip()

    if not grupa or not model:
        return """
        <html><body style="font-family: Arial; text-align:center; margin-top:60px;">
            <h2 style="color:red;">Brak danych</h2>
            <p>Uzupełnij pola: Grupa oraz ModelKolor</p>
            <a href="/" style="font-size:18px;">Wróć</a>
        </body></html>
        """, 400

    conn = db_connect()
    cur = conn.cursor()

    # 1) Jeśli już jest przypisanie -> zwracamy ten sam karton
    cur.execute(
        "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ? LIMIT 1",
        (grupa, model),
    )
    row = cur.fetchone()

    if row:
        karton = row["karton"]
        status = "ZNALEZIONO"
    else:
        # 2) Jeśli brak -> nadaj nowy karton i ZAPISZ
        karton = next_karton_for_group(cur, grupa)
        try:
            cur.execute(
                "INSERT INTO kartony (grupa, modelkolor, karton) VALUES (?, ?, ?)",
                (grupa, model, karton),
            )
            conn.commit()
            status = "NOWY"
        except sqlite3.IntegrityError:
            # ktoś mógł dodać równolegle
            cur.execute(
                "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ? LIMIT 1",
                (grupa, model),
            )
            row2 = cur.fetchone()
            karton = row2["karton"] if row2 else karton
            status = "ZNALEZIONO"

    conn.close()

    # Zapis do historii skanów (ZAWSZE)
    save_scan(grupa, model, karton, status)

    kolor = "#cc0000" if status == "NOWY" else "#0a7a0a"
    opis = "NOWY KARTON PRZYPISANY" if status == "NOWY" else "KARTON JUZ ISTNIEJE"

    return f"""
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Wynik skanu</title>
      </head>
      <body style="font-family: Arial; text-align:center; margin-top:60px;">
        <div style="font-size:18px; color:{kolor}; font-weight:bold;">{opis}</div>
        <h1 style="font-size:56px; color:#cc0000;">KARTON: {karton}</h1>
        <p style="font-size:22px;">Grupa: <b>{grupa}</b></p>
        <p style="font-size:22px;">ModelKolor: <b>{model}</b></p>

        <div style="margin-top:22px;">
          <a href="/" style="font-size:22px; margin-right:16px;">Nowy skan</a>
          <a href="/recent" style="font-size:22px;">Ostatnie 20 skanów</a>
        </div>
      </body>
    </html>
    """


@app.get("/recent")
def recent():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, grupa, modelkolor, karton, status, data
        FROM skany
        ORDER BY id DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()

    # Budujemy tabelkę HTML
    trs = ""
    for r in rows:
        trs += f"""
          <tr>
            <td style="padding:8px; border-bottom:1px solid #ddd;">{r["id"]}</td>
            <td style="padding:8px; border-bottom:1px solid #ddd;"><b>{r["grupa"]}</b></td>
            <td style="padding:8px; border-bottom:1px solid #ddd;">{r["modelkolor"]}</td>
            <td style="padding:8px; border-bottom:1px solid #ddd;"><b>{r["karton"]}</b></td>
            <td style="padding:8px; border-bottom:1px solid #ddd;">{r["status"]}</td>
            <td style="padding:8px; border-bottom:1px solid #ddd;">{r["data"]}</td>
          </tr>
        """

    if not trs:
        trs = """
          <tr>
            <td colspan="6" style="padding:14px; text-align:center;">Brak skanów w historii.</td>
          </tr>
        """

    return f"""
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Ostatnie 20 skanów</title>
      </head>
      <body style="font-family: Arial; margin:30px;">
        <h2 style="text-align:center;">Ostatnie 20 skanów</h2>

        <div style="text-align:center; margin-bottom:18px;">
          <a href="/" style="font-size:18px;">← Wróć do skanowania</a>
        </div>

        <table style="width:100%; border-collapse:collapse; font-size:16px;">
          <thead>
            <tr>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">ID</th>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">Grupa</th>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">ModelKolor</th>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">Karton</th>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">Status</th>
              <th style="text-align:left; padding:8px; border-bottom:2px solid #333;">Data</th>
            </tr>
          </thead>
          <tbody>
            {trs}
          </tbody>
        </table>
      </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
