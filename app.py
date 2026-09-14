import os
from datetime import date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-development-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "library.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(app.instance_path, exist_ok=True)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), default="General")
    isbn = db.Column(db.String(40), unique=True)
    total_copies = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    issued_on = db.Column(db.Date, default=date.today)
    due_on = db.Column(db.Date, nullable=False)
    returned_on = db.Column(db.Date)
    fine = db.Column(db.Integer, default=0)
    book = db.relationship("Book")
    borrower = db.relationship("User")

def current_user():
    if "user_id" not in session:
        return None
    return db.session.get(User, session["user_id"])

@app.context_processor
def inject_user():
    return {"logged_user": current_user()}

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user.role != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Enter your name, a valid email and a password of at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    active_loans = Loan.query.filter_by(returned_on=None).count()
    overdue = Loan.query.filter(Loan.returned_on.is_(None), Loan.due_on < date.today()).count()
    return render_template("dashboard.html",
        book_count=Book.query.count(), member_count=User.query.filter_by(role="student").count(),
        active_loans=active_loans, overdue=overdue,
        recent=Loan.query.order_by(Loan.issued_on.desc()).limit(6).all(),
        today=date.today())
@app.route("/books")
@login_required
def books():
    q = request.args.get("q", "").strip()
    query = Book.query
    if q:
        query = query.filter(db.or_(Book.title.ilike(f"%{q}%"), Book.author.ilike(f"%{q}%"), Book.category.ilike(f"%{q}%")))
    return render_template("books.html", books=query.order_by(Book.title).all(), search=q)

@app.route("/books/add", methods=["POST"])
@admin_required
def add_book():
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    isbn = request.form.get("isbn", "").strip() or None
    try:
        copies = max(1, int(request.form.get("copies", 1)))
    except ValueError:
        copies = 1
    if not title or not author:
        flash("Book title and author are required.", "danger")
    elif isbn and Book.query.filter_by(isbn=isbn).first():
        flash("That ISBN already exists.", "danger")
    else:
        db.session.add(Book(title=title, author=author, category=request.form.get("category", "General").strip() or "General",
                            isbn=isbn, total_copies=copies, available_copies=copies))
        db.session.commit()
        flash("Book added successfully.", "success")
    return redirect(url_for("books"))

@app.route("/books/<int:book_id>/delete", methods=["POST"])
@admin_required
def delete_book(book_id):
    book = db.get_or_404(Book, book_id)
    if Loan.query.filter_by(book_id=book.id, returned_on=None).first():
        flash("Return this book before deleting it.", "warning")
    else:
        Loan.query.filter_by(book_id=book.id).delete()
        db.session.delete(book)
        db.session.commit()
        flash("Book deleted.", "success")
    return redirect(url_for("books"))

@app.route("/members")
@admin_required
def members():
    return render_template("members.html", members=User.query.order_by(User.name).all())

@app.route("/loans")
@login_required
def loans():
    user = current_user()
    query = Loan.query
    if user.role != "admin":
        query = query.filter_by(user_id=user.id)
    return render_template("loans.html", loans=query.order_by(Loan.issued_on.desc()).all(),
                           available_books=Book.query.filter(Book.available_copies > 0).order_by(Book.title).all(),
                           members=User.query.filter_by(role="student").order_by(User.name).all())

@app.route("/loans/issue", methods=["POST"])
@login_required
def issue_book():
    user = current_user()
    try:
        book_id = int(request.form.get("book_id"))
        borrower_id = int(request.form.get("user_id")) if user.role == "admin" else user.id
    except (TypeError, ValueError):
        flash("Choose a valid book and member.", "danger")
        return redirect(url_for("loans"))
    book = db.session.get(Book, book_id)
    borrower = db.session.get(User, borrower_id)
    if not book or not borrower or borrower.role != "student" or book.available_copies < 1:
        flash("The selected book or member is unavailable.", "danger")
    elif Loan.query.filter_by(book_id=book.id, user_id=borrower.id, returned_on=None).first():
        flash("This member already has this book on loan.", "warning")
    else:
        loan = Loan(book_id=book.id, user_id=borrower.id, due_on=date.today() + timedelta(days=14))
        book.available_copies -= 1
        db.session.add(loan)
        db.session.commit()
        flash(f"'{book.title}' issued. Due date: {loan.due_on}.", "success")
    return redirect(url_for("loans"))

@app.route("/loans/<int:loan_id>/return", methods=["POST"])
@login_required
def return_book(loan_id):
    loan = db.get_or_404(Loan, loan_id)
    user = current_user()
    if user.role != "admin" and loan.user_id != user.id:
        flash("You cannot return another member's loan.", "danger")
    elif loan.returned_on:
        flash("This book has already been returned.", "info")
    else:
        loan.returned_on = date.today()
        late_days = max(0, (loan.returned_on - loan.due_on).days)
        loan.fine = late_days * 5
        loan.book.available_copies += 1
        db.session.commit()
        flash(f"Book returned. Fine: ₹{loan.fine}.", "success")
    return redirect(url_for("loans"))

@app.route("/ai")
@login_required
def ai_page():
    return render_template("ai.html")

def local_library_answer(message):
    text = message.lower()
    if any(word in text for word in ["recommend", "suggest", "what should", "looking for"]):
        books = Book.query.filter(Book.available_copies > 0).limit(5).all()
        if books:
            return "Here are some available books you could explore: " + "; ".join(f"{b.title} by {b.author} ({b.category})" for b in books)
        return "There are no books currently available. Please check again later."
    if "overdue" in text or "late" in text or "fine" in text:
        return "Books are normally due 14 days after issue. The current late-return fine is ₹5 per overdue day. Check My Loans for your due dates."
    if "issue" in text or "borrow" in text:
        return "Open Loans, choose an available book and select Issue Book. Students can issue books to themselves; administrators can issue books to any student."
    if "return" in text:
        return "Open Loans and use the Return button next to an active loan. Any overdue fine is calculated automatically at ₹5 per day."
    if "search" in text or "find" in text:
        return "Open Books and use the search field to search by title, author or category."
    return "I am your Library Assistant. I can help you find books, understand borrowing and returns, explain fines, and suggest books. Ask me a library-related question."

@app.route("/api/ai-chat", methods=["POST"])
@login_required
def ai_chat():
    message = (request.json or {}).get("message", "").strip()
    if not message:
        return jsonify({"reply": "Please enter a question."}), 400
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            inventory = Book.query.limit(100).all()
            context = "\n".join(f"{b.title} by {b.author}, category {b.category}, available {b.available_copies}/{b.total_copies}" for b in inventory)
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = ("You are a helpful assistant for this library website. Answer concisely and only make claims supported by this library information. "
                      "Borrowing period is 14 days and overdue fine is ₹5 per day.\nLibrary inventory:\n" + context + "\nUser question: " + message)
            response = model.generate_content(prompt)
            return jsonify({"reply": response.text})
        except Exception:
            app.logger.exception("Gemini request failed; using local assistant.")
    return jsonify({"reply": local_library_answer(message)})

@app.cli.command("create-admin")
def create_admin():
    """Create an administrator account: flask --app app create-admin"""
    import getpass
    name = input("Admin name: ").strip() or "Library Admin"
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (6+ characters): ")
    if len(password) < 6 or User.query.filter_by(email=email).first():
        print("Password too short or email already registered.")
        return
    db.session.add(User(name=name, email=email, password_hash=generate_password_hash(password), role="admin"))
    db.session.commit()
    print("Administrator created.")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
