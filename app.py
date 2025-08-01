from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure Secret Key
app.permanent_session_lifetime = 1800  # 30 minutes session timeout

# Database Connection Function
def get_db_connection():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="12345",
            database="college_db"
        )
        return db
    except mysql.connector.Error as e:
        print("⚠ Database connection failed:", e)
        return None

# ---------------------- SPLASH SCREEN ROUTE ---------------------- #
@app.route("/")
def splash():
    return render_template("splash.html")  # Serve the splash screen

# ---------------------- HOME / LOGIN ROUTE ---------------------- #
@app.route("/home", methods=["GET", "POST"])
def home():
    if "username" in session:
        return render_template("index.html", username=session.get("username"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        db = get_db_connection()
        if not db:
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("home"))

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True  # Keep session active
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("home"))

    return render_template("index.html")  # Login Page

# ---------------------- SIGNUP ROUTE ---------------------- #
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password")

        # Validate Input
        if not username or not email or not password:
            flash("All fields except phone are required!", "danger")
            return redirect(url_for("signup"))

        db = get_db_connection()
        if not db:
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("signup"))

        cursor = db.cursor(dictionary=True)

        # Check if Username Exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already taken. Try another.", "danger")
            return redirect(url_for("signup"))

        # Check Email Usage Limit
        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE email = %s", (email,))
        if cursor.fetchone()["count"] >= 3:
            flash("This email is already used 3 times for registration.", "danger")
            return redirect(url_for("signup"))

        # Hash Password & Insert User
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, email, phone, password) VALUES (%s, %s, %s, %s)",
                       (username, email, phone, hashed_password))
        db.commit()
        cursor.close()
        db.close()

        flash("Signup successful! You can now log in.", "success")
        return redirect(url_for("home"))

    return render_template("signup.html")

# ---------------------- LOGOUT ROUTE ---------------------- #
@app.route("/logout")
def logout():
    if "username" in session:
        session.clear()
        flash("Logged out successfully.", "info")
    else:
        flash("You are not logged in!", "warning")
    return redirect(url_for("home"))

# ---------------------- COLLEGE SEARCH ---------------------- #
@app.route("/predict", methods=["POST"])
def predict():
    if "username" not in session:
        flash("Please log in to search for colleges.", "warning")
        return redirect(url_for("home"))

    try:
        rank = int(request.form.get("rank", 0))
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip().lower()

        if rank <= 0:
            flash("Invalid rank. Please enter a positive number.", "danger")
            return redirect(url_for("home"))

    except ValueError:
        flash("Invalid rank input. Please enter a number.", "danger")
        return redirect(url_for("home"))

    db = get_db_connection()
    if not db:
        flash("Database error. Please try again.", "danger")
        return redirect(url_for("home"))

    cursor = db.cursor(dictionary=True)
    query = """
    SELECT name, location, cutoff_rank, category, image_url, official_website
    FROM colleges 
    WHERE cutoff_rank >= %s 
      AND (category = %s OR category = 'All') 
      AND location LIKE %s
    ORDER BY cutoff_rank ASC
    """
    cursor.execute(query, (rank, category, f"%{location}%"))
    colleges = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("result.html", colleges=colleges)

# ---------------------- RUN APP ---------------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
