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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kartony (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupa TEXT NOT NULL,
            modelkolor TEXT NOT NULL,
            karton TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(grupa, modelkolor)
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
    cur.execute("SELECT karton FROM kartony WHERE grupa = ? ORDER BY id DESC LIMIT 1", (grupa,))
    row = cur.fetchone()

    if not row:
        return f"{grupa}-001"

    last = row["karton"]  # np. ZAK-017
    # Spróbuj wyjąć numer po myślniku
    try:
        num = int(str(last).split("-")[-1])
    except Exception:
        num = 0

    return f"{grupa}-{num + 1:03d}"


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
            <input name="grupa" style="width:260px; height:28px; font-size:16px;" />
          </div>

          <div style="margin:16px;">
            <div style="margin-bottom:6px;">ModelKolor:</div>
            <input name="modelkolor" style="width:260px; height:28px; font-size:16px;" />
          </div>

          <button type="submit" style="width:140px; height:44px; font-size:18px;">Skanuj</button>
        </form>

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
            # W razie gdyby w tym samym czasie ktoś dodał ten sam wpis
            cur.execute(
                "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ? LIMIT 1",
                (grupa, model),
            )
            row2 = cur.fetchone()
            karton = row2["karton"] if row2 else karton
            status = "ZNALEZIONO"

    conn.close()

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
        <br/>
        <a href="/" style="font-size:22px;">Nowy skan</a>
      </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

