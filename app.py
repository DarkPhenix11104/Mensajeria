import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, join_room, emit
import sqlite3

app = Flask(__name__)
app.secret_key = "secreto123"
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= DB =================
def db():
    return sqlite3.connect("mensajeria.db", check_same_thread=False)

def init():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        remitente INTEGER,
        destinatario INTEGER,
        mensaje TEXT
    )
    """)

    con.commit()
    con.close()

init()

# ================= LOGIN =================
@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        con = db()
        cur = con.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (u,p))
        data = cur.fetchone()
        con.close()

        if data:
            session["user_id"] = data[0]
            session["username"] = data[1]
            return redirect("/chat")

    return render_template("login.html")

@app.route("/registro", methods=["GET","POST"])
def registro():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        con = db()
        cur = con.cursor()

        try:
            cur.execute("INSERT INTO usuarios (username,password) VALUES (?,?)",(u,p))
            con.commit()
        except:
            return "Usuario ya existe"

        con.close()
        return redirect("/login")

    return render_template("registro.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= CHAT =================
@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect("/login")

    con = db()
    cur = con.cursor()

    q = request.args.get("q","")

    if q:
        cur.execute("SELECT * FROM usuarios WHERE username LIKE ?",('%'+q+'%',))
    else:
        cur.execute("SELECT * FROM usuarios")

    usuarios = cur.fetchall()
    con.close()

    return render_template("chat.html", usuarios=usuarios)

# ================= CHAT PRIVADO =================
@app.route("/chat/<int:uid>")
def privado(uid):
    if "user_id" not in session:
        return redirect("/login")

    con = db()
    cur = con.cursor()

    cur.execute("SELECT username FROM usuarios WHERE id=?", (uid,))
    user = cur.fetchone()

    if not user:
        con.close()
        return "Usuario no encontrado"

    nombre = user[0]

    cur.execute("""
    SELECT * FROM mensajes
    WHERE (remitente=? AND destinatario=?)
    OR (remitente=? AND destinatario=?)
    """,(session["user_id"],uid,uid,session["user_id"]))

    mensajes = cur.fetchall()
    con.close()

    return render_template("chat_privado.html",
        mensajes=mensajes,
        uid=uid,
        nombre=nombre
    )

# ================= SOCKET =================
@socketio.on("join")
def join(data):
    join_room(data["room"])

@socketio.on("msg")
def mensaje(data):
    try:
        con = db()
        cur = con.cursor()

        cur.execute(
            "INSERT INTO mensajes (remitente,destinatario,mensaje) VALUES (?,?,?)",
            (data["r"], data["d"], data["m"])
        )

        con.commit()
        con.close()

        emit("msg", data, room=data["room"])

    except Exception as e:
        print("ERROR:", e)

# ================= RUN =================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)