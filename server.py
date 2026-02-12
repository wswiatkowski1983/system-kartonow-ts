from flask import Flask, request, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "kartony.db"

# Tworzenie bazy jeśli nie istnieje
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kartony (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupa TEXT,
            modelkolor TEXT,
            karton INTEGER,
            data TEXT
        )
    """)
    conn.commit()
    conn.close()

# Strona główna
@app.route("/", methods=["GET"])
def index():
    return render_template_string("""
    <html>
    <head>
        <title>System Kartonów TS</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family: Arial; text-align:center; margin-top:40px;">
        <h2>System Kartonów TS</h2>
        <form method="post" action="/scan">
            <p>Grupa:</p>
            <input name="grupa" required style="font-size:20px;"><br><br>
            <p>ModelKolor:</p>
            <input name="model" required autofocus style="font-size:20px;"><br><br>
            <button type="submit" style="font-size:20px; padding:10px 20px;">Skanuj</button>
        </form>
    </body>
    </html>
    """)

# Obsługa skanowania
@app.route("/scan", methods=["POST"])
def scan():
    grupa = request.form["grupa"].strip().upper()
    model = request.form["model"].strip().upper()

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Sprawdź czy modelkolor już istnieje
    c.execute("SELECT karton FROM kartony WHERE grupa=? AND modelkolor=?", (grupa, model))
    row = c.fetchone()

    if row:
        karton = row[0]
    else:
        # Pobierz ostatni karton w grupie
        c.execute("SELECT MAX(karton) FROM kartony WHERE grupa=?", (grupa,))
        last = c.fetchone()[0]
        karton = 1 if last is None else last + 1

        # Zapisz nowe przypisanie
        c.execute("""
            INSERT INTO kartony (grupa, modelkolor, karton, data)
            VALUES (?,?,?,?)
        """, (grupa, model, karton, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    conn.close()

    return f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family: Arial; text-align:center; margin-top:60px;">
        <h1 style="font-size:60px; color:red;">KARTON NR: {karton}</h1>
        <p style="font-size:20px;">Grupa: {grupa}</p>
        <p style="font-size:20px;">ModelKolor: {model}</p>
        <br>
        <a href="/" style="font-size:20px;">Nowy skan</a>
    </body>
    </html>
    """

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
