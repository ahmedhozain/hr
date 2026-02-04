from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import os
from sqlalchemy import text, func
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

# Ensure required folders exist and use an absolute DB path (fixes sqlite 'unable to open database file')
import os
basedir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(basedir, ".env"))
instance_dir = os.path.join(basedir, "instance")
uploads_dir = os.getenv("UPLOAD_FOLDER") or os.path.join(basedir, "uploads")
os.makedirs(instance_dir, exist_ok=True)
os.makedirs(uploads_dir, exist_ok=True)

# Replace the original relative URI: app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/app.db"
db_url = os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if "sslmode=" not in db_url and "render.com" in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://ahmed_uv8c_user:Ycp5PKkvYcD3MbgK630brKay8cwr3xg7@dpg-d26fk9bipnbc73b2dvk0-a.oregon-postgres.render.com:5432/ahmed_uv8c?sslmode=require"
app.config["UPLOAD_FOLDER"] = uploads_dir
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["TIMEZONE"] = os.getenv("TIMEZONE", "Africa/Cairo")
try:
    app.config["TIME_OFFSET_HOURS"] = int(os.getenv("TIME_OFFSET_HOURS", "2"))
except Exception:
    app.config["TIME_OFFSET_HOURS"] = 2
try:
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(20 * 1024 * 1024)))
except Exception:
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
_allowed_env = os.getenv("ALLOWED_EXTENSIONS")
ALLOWED_EXTENSIONS = set([e.strip().lower() for e in _allowed_env.split(",")]) if _allowed_env else {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Required document types (Arabic labels)
REQUIRED_DOCS = [
    {"key": "passport", "label": "جواز السفر"},
    {"key": "id_card", "label": "البطاقة الشخصية"},
    {"key": "invitation", "label": "خطاب الدعوة"},
    {"key": "family_record", "label": "القيد العائلي/الفردي"},
    {"key": "bank_statement", "label": "كشف الحساب البنكي"},
    {"key": "employment_proof", "label": "إثبات الوظيفة"},
    {"key": "military_certificate", "label": "شهادة الجيش"},
    {"key": "form", "label": "الفورم"},
    {"key": "photo", "label": "الصورة الشخصية"},
    {"key": "work_history", "label": "سجل العمل لآخر 10 سنوات"}
]
DOC_TYPE_LABELS = {d["key"]: d["label"] for d in REQUIRED_DOCS}

# Jinja filter to render datetimes in local timezone
def format_local(dt, fmt="%Y-%m-%d %H:%M"):
    if not dt:
        return "—"
    try:
        from zoneinfo import ZoneInfo
        tzname = app.config.get("TIMEZONE", "Africa/Cairo")
        tz = ZoneInfo(tzname)
        base = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return base.astimezone(tz).strftime(fmt)
    except Exception:
        try:
            offset = int(app.config.get("TIME_OFFSET_HOURS", 2))
        except Exception:
            offset = 2
        return (dt + timedelta(hours=offset)).strftime(fmt)

@app.template_filter("localtime")
def localtime_filter(dt):
    return format_local(dt)

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash("الملف أكبر من الحد المسموح (20MB)")
    return redirect(request.referrer or url_for("client"))

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Automatic one-time rename of existing tables to new names
def _rename_tables_if_needed():
    try:
        with db.engine.connect() as conn:
            hr_users_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='hr_users')")).scalar()
            user_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='user')")).scalar()
            if not hr_users_exists and user_exists:
                conn.execute(text('ALTER TABLE "user" RENAME TO hr_users'))
            hr_docs_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='hr_documents')")).scalar()
            doc_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='document')")).scalar()
            if not hr_docs_exists and doc_exists:
                conn.execute(text("ALTER TABLE document RENAME TO hr_documents"))
    except Exception:
        # Non-fatal: app can still run; failures logged when DEBUG
        if app.config.get("FLASK_ENV") == "development":
            print("Table rename check failed")

_rename_tables_if_needed()

class User(UserMixin, db.Model):
    __tablename__ = "hr_users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))  # client / admin / supervisor
    name = db.Column(db.String(120), nullable=True)
    documents = db.relationship("Document", backref="user", lazy=True, cascade="all, delete-orphan")

class Document(db.Model):
    __tablename__ = "hr_documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("hr_users.id"), nullable=False)
    doc_type = db.Column(db.String(50), nullable=True)
    filename = db.Column(db.String(200))
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.Text, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"]).first()
        if u and check_password_hash(u.password, request.form["password"]):
            remember = bool(request.form.get("remember"))
            login_user(u, remember=remember)
            # Redirect using url_for to avoid path issues and ensure correct endpoint resolution
            return redirect(url_for("client") if u.role == "client" else url_for("admin") if u.role == "admin" else url_for("supervisor"))
        flash("Login failed")
    # If already logged in, go directly to the main page for the user role
    if current_user.is_authenticated:
        return redirect(url_for("client") if current_user.role == "client" else url_for("admin") if current_user.role == "admin" else url_for("supervisor"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    # Use url_for for consistency
    return redirect(url_for("login"))

@app.route("/client", methods=["GET","POST"])
@login_required
def client():
    if current_user.role != "client":
        return "Forbidden"
    if request.method == "POST":
        doc_type = (request.form.get("doc_type") or "").strip()
        valid_types = {d["key"] for d in REQUIRED_DOCS}
        if not doc_type or doc_type not in valid_types:
            flash("الرجاء اختيار نوع مستند صالح")
            return redirect(request.form.get("next") or request.referrer or url_for("client"))
        f = request.files.get("file")
        if not f or not f.filename or f.filename.strip() == "":
            flash("يجب اختيار ملف")
            return redirect(request.form.get("next") or request.referrer or url_for("client"))
        if not allowed_file(f.filename):
            flash("الرجاء رفع ملف بصيغة مسموحة: PDF أو صورة (PNG, JPG, JPEG)")
            return redirect(request.form.get("next") or request.referrer or url_for("client"))
        name = secure_filename(f.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], name)
        # If user already has a document for this type, replace it
        existing = Document.query.filter_by(user_id=current_user.id, doc_type=doc_type).first()
        if existing:
            try:
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], existing.filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass
            f.save(path)
            existing.filename = name
            existing.status = "pending"
            existing.reviewed_at = None
            existing.reason = None
            existing.created_at = datetime.utcnow()
            db.session.commit()
            flash("تم استبدال الملف بنجاح")
        else:
            f.save(path)
            d = Document(user_id=current_user.id, doc_type=doc_type, filename=name)
            db.session.add(d)
            db.session.commit()
            flash("تم رفع الملف بنجاح")
    # Build mapping of docs by type for this client
    docs = Document.query.filter_by(user_id=current_user.id).all()
    docs_by_type = {}
    for d in docs:
        if d.doc_type:
            docs_by_type[d.doc_type] = d
    return render_template("client.html", docs=docs, required_docs=REQUIRED_DOCS, docs_by_type=docs_by_type)

@app.route("/client/docs/<int:id>/replace", methods=["POST"], endpoint="client_replace")
@login_required
def client_replace(id):
    if current_user.role != "client":
        return "Forbidden"
    d = Document.query.get_or_404(id)
    if d.user_id != current_user.id:
        return "Forbidden"
    f = request.files.get("file")
    if not f or f.filename.strip() == "":
        flash("يجب اختيار ملف")
        return redirect(request.form.get("next") or request.referrer or url_for("client"))
    if not allowed_file(f.filename):
        flash("الرجاء رفع ملف بصيغة مسموحة: PDF أو صورة (PNG, JPG, JPEG)")
        return redirect(request.form.get("next") or request.referrer or url_for("client"))
    name = secure_filename(f.filename)
    new_path = os.path.join(app.config["UPLOAD_FOLDER"], name)
    try:
        old_path = os.path.join(app.config["UPLOAD_FOLDER"], d.filename)
        if os.path.exists(old_path):
            os.remove(old_path)
    except Exception:
        pass
    f.save(new_path)
    d.filename = name
    d.status = "pending"
    d.reviewed_at = None
    d.reason = None
    d.created_at = datetime.utcnow()
    db.session.commit()
    flash("تم إعادة رفع الملف")
    next_url = request.form.get("next") or request.referrer or url_for("client")
    return redirect(next_url)

@app.route("/admin", methods=["GET","POST"])
@login_required
def admin():
    if current_user.role not in ["admin", "supervisor"]:
        return "Forbidden"
    if request.method == "POST":
        if current_user.role != "admin":
            flash("غير مسموح")
            return redirect(request.form.get("next") or request.referrer or url_for("admin"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        if not name or not email or not password or role not in ["client", "supervisor"]:
            flash("بيانات غير صحيحة")
            return redirect(request.form.get("next") or request.referrer or url_for("admin"))
        if User.query.filter_by(email=email).first():
            flash("المستخدم موجود بالفعل")
            return redirect(request.form.get("next") or request.referrer or url_for("admin"))
        u = User(name=name, email=email, password=generate_password_hash(password), role=role)
        db.session.add(u)
        db.session.commit()
        flash("تم إنشاء المستخدم بنجاح")
        return redirect(request.form.get("next") or request.referrer or url_for("admin"))
    docs = Document.query.all()
    users_by_id = {u.id: (u.name or u.email) for u in User.query.all()}
    users = User.query.order_by(User.id.desc()).all()
    # Aggregate clients who have files with counts and last upload time
    agg = db.session.query(
        Document.user_id,
        func.count(Document.id).label("file_count"),
        func.max(Document.created_at).label("last_upload")
    ).group_by(Document.user_id).all()
    clients_info = []
    for row in agg:
        u = User.query.get(row.user_id)
        if u:
            clients_info.append({
                "id": u.id,
                "name": u.name or u.email,
                "email": u.email,
                "file_count": row.file_count,
                "last_upload": row.last_upload
            })
    latest_docs = Document.query.order_by(Document.created_at.desc()).limit(10).all()
    return render_template("admin.html", docs=docs, users_by_id=users_by_id, users=users, clients_info=clients_info, latest_docs=latest_docs, doc_type_labels=DOC_TYPE_LABELS)

@app.route("/admin/manage")
@login_required
def admin_manage():
    if current_user.role != "admin":
        return "Forbidden"
    users = User.query.order_by(User.id.desc()).all()
    return render_template("admin_manage.html", users=users)

@app.route("/admin/password/change", methods=["POST"])
@login_required
def admin_change_password():
    if current_user.role != "admin":
        flash("غير مسموح")
        return redirect(request.form.get("next") or request.referrer or url_for("admin"))
    email = (request.form.get("email") or "").strip()
    new_password = (request.form.get("new_password") or "").strip()
    if not email or not new_password:
        flash("بيانات غير صحيحة")
        return redirect(request.form.get("next") or request.referrer or url_for("admin_manage"))
    u = User.query.filter_by(email=email).first()
    if not u:
        flash("غير متاح")
        return redirect(request.form.get("next") or request.referrer or url_for("admin_manage"))
    u.password = generate_password_hash(new_password)
    db.session.commit()
    flash("تم تغيير كلمة المرور")
    return redirect(request.form.get("next") or request.referrer or url_for("admin_manage"))

@app.route("/admin/users/<int:id>/delete", methods=["POST"])
@login_required
def delete_user(id):
    if current_user.role != "admin":
        flash("غير مسموح")
        return redirect(request.form.get("next") or request.referrer or url_for("admin"))
    if current_user.id == id:
        flash("لا يمكنك حذف نفسك")
        return redirect(request.form.get("next") or request.referrer or url_for("admin"))
    u = User.query.get_or_404(id)
    if u.role == "admin":
        flash("لا يمكن حذف مدير")
        return redirect(request.form.get("next") or request.referrer or url_for("admin"))
    docs = Document.query.filter_by(user_id=id).all()
    for d in docs:
        try:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], d.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        db.session.delete(d)
    db.session.delete(u)
    db.session.commit()
    flash("تم حذف المستخدم وكل ملفاته")
    return redirect(request.form.get("next") or request.referrer or url_for("admin"))

@app.route("/supervisor")
@login_required
def supervisor():
    if current_user.role != "supervisor":
        return "Forbidden"
    docs = Document.query.all()
    users_by_id = {u.id: (u.name or u.email) for u in User.query.all()}
    # Aggregate clients who have files
    agg = db.session.query(
        Document.user_id,
        func.count(Document.id).label("file_count"),
        func.max(Document.created_at).label("last_upload")
    ).group_by(Document.user_id).all()
    clients_info = []
    for row in agg:
        u = User.query.get(row.user_id)
        if u:
            clients_info.append({
                "id": u.id,
                "name": u.name or u.email,
                "email": u.email,
                "file_count": row.file_count,
                "last_upload": row.last_upload
            })
    latest_docs = Document.query.order_by(Document.created_at.desc()).limit(10).all()
    return render_template("supervisor.html", docs=docs, users_by_id=users_by_id, clients_info=clients_info, latest_docs=latest_docs, doc_type_labels=DOC_TYPE_LABELS)

@app.route("/review/<int:id>/<status>")
@login_required
def review(id, status):
    if current_user.role not in ["admin", "supervisor"]:
        return "Forbidden"
    d = Document.query.get_or_404(id)
    d.status = status
    if status in ["approved", "rejected"]:
        d.reviewed_at = datetime.utcnow()
    else:
        d.reviewed_at = None
    # Clear any previous rejection reason when approving or setting pending
    if status in ["approved", "pending"]:
        d.reason = None
    db.session.commit()
    next_url = request.args.get("next") or request.referrer or (url_for("admin") if current_user.role == "admin" else url_for("supervisor"))
    return redirect(next_url)

@app.route("/review/<int:id>/reject", methods=["POST"])
@login_required
def review_reject(id):
    if current_user.role not in ["admin", "supervisor"]:
        return "Forbidden"
    d = Document.query.get_or_404(id)
    reason = request.form.get("reason", "").strip()
    d.status = "rejected"
    d.reviewed_at = datetime.utcnow()
    d.reason = reason if reason else None
    db.session.commit()
    next_url = request.form.get("next") or request.referrer or (url_for("admin") if current_user.role == "admin" else url_for("supervisor"))
    return redirect(next_url)

@app.route("/files/<name>")
@login_required
def files(name):
    doc = Document.query.filter_by(filename=name).first_or_404()
    if current_user.role in ["admin", "supervisor"] or current_user.id == doc.user_id:
        # Force download when using the 'تحميل' button
        return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=True)
    return "Forbidden", 403

@app.route("/preview/<name>")
@login_required
def preview_file(name):
    doc = Document.query.filter_by(filename=name).first_or_404()
    if current_user.role in ["admin", "supervisor"] or current_user.id == doc.user_id:
        import mimetypes
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        # Allow preview for PDFs, images, and text files; otherwise show an informative page
        allow_inline = False
        try:
            allow_inline = mime.startswith("image/") or mime.startswith("text/") or mime == "application/pdf"
        except Exception:
            allow_inline = False
        if allow_inline:
            return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=False, mimetype=mime)
        else:
            return render_template("preview_unsupported.html", filename=name)
    return "Forbidden", 403

# Route: show all documents for a specific client (admin/supervisor only)
@app.route("/clients/<int:user_id>")
@login_required
def client_docs(user_id):
    if current_user.role not in ["admin", "supervisor"]:
        return "Forbidden"
    user = User.query.get_or_404(user_id)
    docs = Document.query.filter_by(user_id=user_id).order_by(Document.created_at.desc()).all()
    return render_template("client_detail.html", user=user, docs=docs, doc_type_labels=DOC_TYPE_LABELS)
    
with app.app_context():
    db.create_all()
    # شغّل مساعدات ترقية SQLite فقط عند استخدام SQLite لتفادي أخطاء على PostgreSQL
    bind = db.session.get_bind() or db.engine
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "sqlite":
        try:
            cols = [row[1] for row in db.session.execute(text("PRAGMA table_info(document)")).fetchall()]
            if "created_at" not in cols:
                db.session.execute(text("ALTER TABLE document ADD COLUMN created_at DATETIME"))
            if "reviewed_at" not in cols:
                db.session.execute(text("ALTER TABLE document ADD COLUMN reviewed_at DATETIME"))
            if "reason" not in cols:
                db.session.execute(text("ALTER TABLE document ADD COLUMN reason TEXT"))
            if "doc_type" not in cols:
                db.session.execute(text("ALTER TABLE document ADD COLUMN doc_type VARCHAR(50)"))
            db.session.commit()
        except Exception:
            pass
        try:
            ucols = [row[1] for row in db.session.execute(text("PRAGMA table_info(user)")).fetchall()]
            if "name" not in ucols:
                db.session.execute(text("ALTER TABLE user ADD COLUMN name VARCHAR(120)"))
            db.session.commit()
        except Exception:
            pass
    if not User.query.filter_by(email="admin@test.com").first():
        db.session.add(User(email="admin@test.com", name="مدير", password=generate_password_hash("123"), role="admin"))
        db.session.add(User(email="client@test.com", name="عميل", password=generate_password_hash("123"), role="client"))
        db.session.add(User(email="supervisor@test.com", name="مشرف", password=generate_password_hash("123"), role="supervisor"))
        db.session.commit()

    

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
  