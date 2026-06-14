from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import csv
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = 1800  # 30 minutes

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "college.db")

# ---------------------- DATABASE CONNECTION & INIT ---------------------- #
def get_db_connection():
    try:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        return db
    except sqlite3.Error as e:
        print("[DB Connection Error] Database connection failed:", e)
        return None

def init_db():
    db = get_db_connection()
    if not db:
        print("[DB Init Error] Could not initialize database.")
        return
    cursor = db.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            password TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colleges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            category TEXT NOT NULL,
            tier TEXT,
            cutoff_rank INTEGER NOT NULL,
            fees INTEGER,
            placements TEXT,
            image_url TEXT,
            official_website TEXT
        )
    """)
    db.commit()

    # Seed data if empty
    cursor.execute("SELECT COUNT(*) AS count FROM colleges")
    count = cursor.fetchone()["count"]
    if count == 0:
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c.csv")
        if os.path.exists(csv_path):
            print("[DB Seeding] Seeding colleges from c.csv...")
            try:
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row["name"].strip()
                        location = row["location"].strip()
                        category = row["category"].strip()
                        tier = row["tier"].strip() if row.get("tier") else ""
                        
                        # Infer tier if NULL or empty
                        if not tier or tier == "NULL":
                            name_lower = name.lower()
                            if any(k in name_lower for k in ["iit", "bits pilani", "dtu", "nsut", "warangal", "trichy", "surathkal", "iiit hyderabad"]):
                                tier = "Tier 1"
                            elif any(k in name_lower for k in ["nit", "iiit", "andhra university", "jntu", "osmania", "manipal"]):
                                tier = "Tier 2"
                            else:
                                tier = "Tier 3"
                        
                        cutoff_rank = int(row["cutoff_rank"]) if row["cutoff_rank"] else 999999
                        fees = int(row["fees"]) if row["fees"] and row["fees"] != "NULL" else 0
                        placements = row["placements"].strip() if row.get("placements") else ""
                        image_url = row["image_url"].strip() if row.get("image_url") else ""
                        official_website = row["official_website"].strip() if row.get("official_website") else ""
                        
                        # Map example image URLs to local images
                        if "example.com/image" in image_url:
                            img_match = re.search(r"image(\d+)\.jpg", image_url)
                            if img_match:
                                num = img_match.group(1)
                                image_url = f"/static/images/image{num}.jpeg"
                        
                        cursor.execute("""
                            INSERT INTO colleges (name, location, category, tier, cutoff_rank, fees, placements, image_url, official_website)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (name, location, category, tier, cutoff_rank, fees, placements, image_url, official_website))
                db.commit()
                print("[DB Seeding] Database seeded successfully!")
            except Exception as e:
                db.rollback()
                print("[DB Seeding Error] Error seeding colleges:", e)
        else:
            print("[DB Seeding Warning] c.csv not found, skipping seeding.")
            
    cursor.close()
    db.close()

# Initialize the database immediately on import
init_db()



# ---------------------- SPLASH SCREEN ---------------------- #
@app.route("/")
def splash():
    return render_template("splash.html")


# ---------------------- LOGIN / HOME ---------------------- #
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

        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("home"))

    return render_template("index.html")


# ---------------------- SIGNUP ---------------------- #
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields except phone are required!", "danger")
            return redirect(url_for("signup"))

        db = get_db_connection()
        if not db:
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("signup"))

        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            flash("Username already taken. Try another.", "danger")
            return redirect(url_for("signup"))

        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE email = ?", (email,))
        email_count = cursor.fetchone()["count"]
        if email_count >= 3:
            flash("This email is already used 3 times for registration.", "danger")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
            (username, email, phone, hashed_password)
        )
        db.commit()
        cursor.close()
        db.close()

        flash("Signup successful! You can now log in.", "success")
        return redirect(url_for("home"))

    return render_template("signup.html")


# ---------------------- LOGOUT ---------------------- #
@app.route("/logout")
def logout():
    if "username" in session:
        session.clear()
        flash("Logged out successfully.", "info")
    else:
        flash("You are not logged in!", "warning")
    return redirect(url_for("home"))


# ---------------------- LOCATION EXPANSION HELPER ---------------------- #
def expand_location(loc_input):
    loc_lower = loc_input.lower().strip()
    
    state_map = {
        'telangana': ['Hyderabad', 'Warangal'],
        'ts': ['Hyderabad', 'Warangal'],
        'andhra pradesh': ['Visakhapatnam', 'Kakinada', 'Amaravati', 'Anantapur', 'Tirupati'],
        'ap': ['Visakhapatnam', 'Kakinada', 'Amaravati', 'Anantapur', 'Tirupati'],
        'andhra': ['Visakhapatnam', 'Kakinada', 'Amaravati', 'Anantapur', 'Tirupati'],
        'karnataka': ['Bangalore', 'Surathkal', 'Manipal'],
        'ka': ['Bangalore', 'Surathkal', 'Manipal'],
        'tamil nadu': ['Chennai', 'Trichy', 'Vellore'],
        'tn': ['Chennai', 'Trichy', 'Vellore'],
        'delhi': ['Delhi'],
        'ncr': ['Delhi'],
        'maharashtra': ['Mumbai', 'Pune'],
        'mh': ['Mumbai', 'Pune'],
        'west bengal': ['Kharagpur', 'Durgapur'],
        'wb': ['Kharagpur', 'Durgapur'],
        'uttar pradesh': ['Kanpur', 'Allahabad'],
        'up': ['Kanpur', 'Allahabad'],
        'rajasthan': ['Pilani', 'Jaipur'],
        'rj': ['Pilani', 'Jaipur'],
        'madhya pradesh': ['Gwalior', 'Bhopal', 'Jabalpur'],
        'mp': ['Gwalior', 'Bhopal', 'Jabalpur'],
        'orissa': ['Rourkela', 'Bhubaneswar'],
        'odisha': ['Rourkela', 'Bhubaneswar'],
        'bihar': ['Patna'],
        'assam': ['Guwahati', 'Silchar'],
        'kerala': ['Calicut'],
        'kl': ['Calicut']
    }
    
    if loc_lower in state_map:
        return state_map[loc_lower]
    return [loc_input]


# ---------------------- COLLEGE SEARCH ---------------------- #
@app.route("/predict", methods=["POST"])
def predict():
    if "username" not in session:
        flash("Please log in to search for colleges.", "warning")
        return redirect(url_for("home"))

    try:
        # Get form data
        name = request.form.get("name", "").strip()
        hallticket = request.form.get("hallticket", "").strip()
        gender = request.form.get("gender", "").strip()         # for display only
        exam_type = request.form.get("exam_type", "").strip()   # for display only
        college_type = request.form.get("college_type", "").strip()
        location = request.form.get("location", "").strip()
        rank = int(request.form.get("rank", 0))
        category = request.form.get("category", "").strip()

        # Validate
        if not name or not hallticket:
            flash("Please fill in all required details!", "danger")
            return redirect(url_for("home"))

        if rank <= 0:
            flash("Invalid rank. Please enter a positive number.", "danger")
            return redirect(url_for("home"))

        # Default location to 'All' if user left it blank
        if not location:
            location = "All"

    except ValueError:
        flash("Invalid rank input. Please enter a number.", "danger")
        return redirect(url_for("home"))

    db = get_db_connection()
    if not db:
        flash("Database connection error. Try again later.", "danger")
        return redirect(url_for("home"))

    cursor = db.cursor()

    # Rule-based category mapping
    category_map = {
        'OC': ['General', 'All', 'Govt', 'Pvt', 'OC'],
        'BC': ['OBC', 'General', 'All', 'Govt', 'Pvt', 'BC'],
        'SC': ['SC', 'General', 'All', 'Govt', 'Pvt', 'SC'],
        'ST': ['ST', 'General', 'All', 'Govt', 'Pvt', 'ST'],
        'EWS': ['EWS', 'General', 'All', 'Govt', 'Pvt', 'EWS']
    }
    mapped_categories = category_map.get(category, [category, 'All'])
    placeholders = ", ".join("?" for _ in mapped_categories)
    
    # Query parameters for primary query
    params = [rank] + mapped_categories
    cities = expand_location(location)

    # ✅ Handle both 'All' and specific location cases with SQLite syntax
    if len(cities) == 1 and cities[0].lower() == "all":
        query = f"""
            SELECT name, location, category, cutoff_rank, fees, placements,
                   image_url, official_website, tier
            FROM colleges
            WHERE cutoff_rank >= ?
              AND category IN ({placeholders})
              AND (tier = ? OR ? = 'All')
            ORDER BY cutoff_rank ASC
        """
        params.extend([college_type, college_type])
    else:
        # Build OR condition for multiple location options (e.g. location LIKE ? OR location LIKE ?)
        loc_clauses = " OR ".join("location LIKE ?" for _ in cities)
        query = f"""
            SELECT name, location, category, cutoff_rank, fees, placements,
                   image_url, official_website, tier
            FROM colleges
            WHERE cutoff_rank >= ?
              AND category IN ({placeholders})
              AND ({loc_clauses})
              AND (tier = ? OR ? = 'All')
            ORDER BY cutoff_rank ASC
        """
        for city in cities:
            params.append(f"%{city}%")
        params.extend([college_type, college_type])

    cursor.execute(query, params)
    colleges = [dict(row) for row in cursor.fetchall()]

    # Fallback recommendations if zero strict matches are found
    suggested_colleges = []
    stretch_colleges = []
    
    if not colleges:
        # Fallback 1: Ignore location restrictions (suggest colleges in other regions matching user's rank/tier)
        suggested_params = [rank] + mapped_categories + [college_type, college_type]
        suggested_query = f"""
            SELECT name, location, category, cutoff_rank, fees, placements,
                   image_url, official_website, tier
            FROM colleges
            WHERE cutoff_rank >= ?
              AND category IN ({placeholders})
              AND (tier = ? OR ? = 'All')
            ORDER BY cutoff_rank ASC
            LIMIT 6
        """
        cursor.execute(suggested_query, suggested_params)
        suggested_colleges = [dict(row) for row in cursor.fetchall()]

        # Fallback 2: Ambitious choices in preferred location (allow cutoffs up to 30% lower than user's rank)
        if len(cities) == 1 and cities[0].lower() == "all":
            # No location stretch needed since Fallback 1 already covers all locations
            pass
        else:
            stretch_rank = int(rank * 0.7)
            stretch_params = [stretch_rank] + mapped_categories
            loc_clauses = " OR ".join("location LIKE ?" for _ in cities)
            
            stretch_query = f"""
                SELECT name, location, category, cutoff_rank, fees, placements,
                       image_url, official_website, tier
                FROM colleges
                WHERE cutoff_rank >= ?
                  AND category IN ({placeholders})
                  AND ({loc_clauses})
                  AND (tier = ? OR ? = 'All')
                ORDER BY cutoff_rank ASC
                LIMIT 6
            """
            for city in cities:
                stretch_params.append(f"%{city}%")
            stretch_params.extend([college_type, college_type])
            
            cursor.execute(stretch_query, stretch_params)
            stretch_colleges = [dict(row) for row in cursor.fetchall()]

    cursor.close()
    db.close()

    return render_template(
        "result.html",
        colleges=colleges,
        suggested_colleges=suggested_colleges,
        stretch_colleges=stretch_colleges,
        name=name,
        hallticket=hallticket,
        gender=gender,
        exam_type=exam_type,
        college_type=college_type,
        location=location,
        rank=rank,
        category=category
    )


# ---------------------- RUN APP ---------------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
