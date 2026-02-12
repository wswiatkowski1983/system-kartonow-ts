import os
import sqlite3
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)

# =========================
# BAZA DANYCH (SQLite)
# =========================
# Na Render najlepiej trzymać DB w katalogu aplikacji.
# Uwaga: na darmowym planie Render instancja może być resetowana, więc dane mogą zniknąć po restarcie.
APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "kartony.db"


def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kartony (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupa TEXT NOT NULL,
            modelkolor TEXT NOT NULL,
            karton TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


# Utwórz tabelę od razu przy starcie aplikacji (to naprawia błąd "no such table: kartony")
init_db()


# =========================
# STRONA GŁÓWNA (FORMULARZ)
# =========================
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

          <button type="submit" style="width:120px; height:40px; font-size:16px;">Skanuj</button>
        </form>

      </body>
    </html>
    """


# =========================
# SKAN (POST)
# =========================
@app.route("/scan", methods=["POST", "GET"])
def scan():
    # Jeśli ktoś wejdzie GETem w /scan, odsyłamy na stronę główną
    if request.method == "GET":
        return home()

    grupa = (request.form.get("grupa") or "").strip()
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

    # Jeśli masz mapowanie w bazie (grupa + modelkolor -> karton), to to pobieramy:
    cur.execute(
        "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ? ORDER BY id DESC LIMIT 1",
        (grupa, model),
    )
    row = cur.fetchone()

    if row:
        karton = row["karton"]
    else:
        # Jeśli nie ma wpisu w bazie, dajemy czytelny komunikat
        karton = "BRAK W BAZIE"

    conn.close()

    return f"""
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Wynik skanu</title>
      </head>
      <body style="font-family: Arial; text-align:center; margin-top:60px;">
        <h1 style="font-size:56px; color:#cc0000;">KARTON: {karton}</h1>
        <p style="font-size:22px;">Grupa: <b>{grupa}</b></p>
        <p style="font-size:22px;">ModelKolor: <b>{model}</b></p>
        <br/>
        <a href="/" style="font-size:22px;">Nowy skan</a>
      </body>
    </html>
    """


# =========================
# START (LOCAL)
# Render używa PORT z env, więc to tylko dla lokalnego uruchomienia
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
