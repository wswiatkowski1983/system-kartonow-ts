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

    # tabela mapowania
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
    cur.execute(
        "SELECT karton FROM kartony WHERE grupa = ? ORDER BY id DESC LIMIT 1",
        (grupa,)
    )
    row = cur.fetchone()

    if not row:
        return f"{grupa}-001"

    last = row["karton"]
    try:
        num = int(str(last).split("-")[-1])
    except:
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
    <body style="font-family: Arial; text-align:center; margin-top:40px;">

        <h2>System Kartonów TS</h2>

        <form method="POST" action="/scan">
            <div style="margin:12px;">
                <div>Grupa:</div>
                <input id="grupa" name="grupa"
                       style="width:260px; height:32px; font-size:18px;" />
            </div>

            <div style="margin:12px;">
                <div>Skanuj Model/EAN:</div>
                <input id="modelkolor" name="modelkolor" autofocus
                       style="width:260px; height:32px; font-size:20px;" />
            </div>

            <button type="submit"
                    style="width:200px; height:45px; font-size:18px;">
                Skanuj
            </button>
        </form>

        <script>
            const grupaInput = document.getElementById("grupa");
            const modelInput = document.getElementById("modelkolor");

            // zapamiętaj grupę
            const saved = localStorage.getItem("grupa");
            if(saved){
                grupaInput.value = saved;
            }

            grupaInput.addEventListener("input", function(){
                localStorage.setItem("grupa", grupaInput.value);
            });

            window.onload = function(){
                modelInput.focus();
            }
        </script>

    </body>
    </html>
    """


@app.route("/scan", methods=["POST"])
def scan():
    grupa = (request.form.get("grupa") or "").strip().upper()
    model = (request.form.get("modelkolor") or "").strip()

    if not grupa or not model:
        return '<script>window.location.href="/"</script>'

    conn = db_connect()
    cur = conn.cursor()

    # sprawdz czy już istnieje przypisanie
    cur.execute(
        "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ?",
        (grupa, model)
    )
    row = cur.fetchone()

    if row:
        karton = row["karton"]
    else:
        karton = next_karton_for_group(cur, grupa)
        try:
            cur.execute(
                "INSERT INTO kartony (grupa, modelkolor, karton) VALUES (?, ?, ?)",
                (grupa, model, karton),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # jeśli w międzyczasie ktoś dodał
            cur.execute(
                "SELECT karton FROM kartony WHERE grupa = ? AND modelkolor = ?",
                (grupa, model)
            )
            karton = cur.fetchone()["karton"]

    conn.close()

    return f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="1;url=/" />
    </head>
    <body style="font-family: Arial; text-align:center; margin-top:60px;">
        <h1 style="font-size:60px; color:red;">{karton}</h1>
    </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

