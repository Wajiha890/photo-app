from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
from models import db, Image, Comment, Rating, User, Reaction
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, text
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
import jwt
import datetime
import os
import uuid
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
MAX_MEDIA_SIZE = 50 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image", "video"}
ALLOWED_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "gif", "webp"},
    "video": {"mp4", "webm", "ogg", "mov"},
}
ALLOWED_MIME_PREFIXES = {"image": "image/", "video": "video/"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

_cors_raw = str(app.config.get("CORS_ORIGINS_RAW", "*")).strip()
if _cors_raw == "*":
    CORS(app, resources={r"/*": {"origins": "*"}})
else:
    _origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    CORS(app, resources={r"/*": {"origins": _origins if _origins else "*"}})


# JWT Helpers
def create_token(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=app.config["JWT_EXPIRY_HOURS"])
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except:
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        if not token:
            return jsonify({"message": "Token missing"}), 401
        data = decode_token(token)
        if not data:
            return jsonify({"message": "Token invalid or expired"}), 401
        request.user_id = data["user_id"]
        request.user_role = data["role"]
        return f(*args, **kwargs)
    return decorated


def creator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        if not token:
            return jsonify({"message": "Token missing"}), 401
        data = decode_token(token)
        if not data or data["role"] != "creator":
            return jsonify({"message": "Creator access required"}), 403
        request.user_id = data["user_id"]
        request.user_role = data["role"]
        return f(*args, **kwargs)
    return decorated


def get_optional_user_id():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return None
    data = decode_token(token)
    return data.get("user_id") if data else None


def allowed_file(filename, media_type):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(media_type, set())


def validate_media_url(url):
    return url.startswith("http://") or url.startswith("https://")


def save_uploaded_media(file, media_type):
    if not file or not file.filename:
        return None, "Media file is required"
    if media_type not in ALLOWED_MEDIA_TYPES:
        return None, "Media type must be image or video"
    if not allowed_file(file.filename, media_type):
        return None, f"Unsupported {media_type} file type"
    if file.content_type and not file.content_type.startswith(ALLOWED_MIME_PREFIXES[media_type]):
        return None, f"Selected file does not match {media_type} media type"

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_MEDIA_SIZE:
        return None, "File is too large. Maximum size is 50MB"

    original = secure_filename(file.filename)
    ext = original.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    # --- Azure Blob Storage (private container + SAS URL) ---
    conn_str = app.config.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if conn_str:
        try:
            blob_service  = BlobServiceClient.from_connection_string(conn_str)
            blob_client   = blob_service.get_blob_client(container="media", blob=filename)
            content_type  = file.content_type or ("image/jpeg" if media_type == "image" else "video/mp4")
            blob_client.upload_blob(
                file.stream,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
            # Generate a read-only SAS URL valid for 5 years
            sas_token = generate_blob_sas(
                account_name=blob_service.account_name,
                container_name="media",
                blob_name=filename,
                account_key=blob_service.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.datetime.utcnow() + datetime.timedelta(days=1825)
            )
            sas_url = (
                f"https://{blob_service.account_name}.blob.core.windows.net"
                f"/media/{filename}?{sas_token}"
            )
            return sas_url, None
        except Exception as e:
            return None, f"Azure Storage upload failed: {str(e)}"

    # --- Local fallback (dev without Azure) ---
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return request.host_url.rstrip("/") + "/uploads/" + filename, None


# HEALTH
@app.route("/")
def home():
    return jsonify({"message": "PixShare API Running ✨"})


@app.route("/uploads/<path:filename>")
def uploaded_media(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# AUTH ROUTES (same as before)
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already taken"}), 409

    hashed = generate_password_hash(password)
    user = User(username=username, password=hashed, role="consumer")
    db.session.add(user)
    db.session.commit()
    token = create_token(user.id, user.role)
    return jsonify({"message": "Account created", "token": token, "role": user.role, "username": user.username}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        token = create_token(user.id, user.role)
        return jsonify({"message": "Login successful", "token": token, "role": user.role, "username": user.username})
    return jsonify({"message": "Invalid credentials"}), 401


@app.route("/me", methods=["GET"])
@token_required
def me():
    user = User.query.get(request.user_id)
    return jsonify({"id": user.id, "username": user.username, "role": user.role})


# IMAGE ROUTES (same)
def image_to_dict(img, user_id=None):
    ratings = [r.value for r in img.ratings]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    my_rating = None
    if user_id:
        my_rating_row = Rating.query.filter_by(image_id=img.id, user_id=user_id).first()
        if my_rating_row:
            my_rating = my_rating_row.value
    reaction_counts = {"like": 0, "happy": 0, "love": 0}
    my_reaction = None
    for reaction in img.reactions:
        if reaction.reaction_type in reaction_counts:
            reaction_counts[reaction.reaction_type] += 1
        if user_id and reaction.user_id == user_id:
            my_reaction = reaction.reaction_type

    return {
        "id": img.id, "title": img.title, "caption": img.caption,
        "location": img.location, "people": img.people, "image_url": img.image_url,
        "media_url": img.image_url, "media_type": getattr(img, "media_type", "image"),
        "upload_method": getattr(img, "upload_method", "url"),
        "created_at": img.created_at.isoformat() if img.created_at else None,
        "uploader": img.uploader.username if img.uploader else "Unknown",
        "avg_rating": avg_rating, "rating_count": len(ratings), "comment_count": len(img.comments),
        "reaction_counts": reaction_counts,
        "my_reaction": my_reaction,
        "my_rating": my_rating,
    }

@app.route("/images", methods=["GET"])
def get_images():
    user_id = get_optional_user_id()
    images = Image.query.order_by(Image.created_at.desc()).all()
    return jsonify([image_to_dict(img, user_id) for img in images])

@app.route("/images/<int:image_id>", methods=["GET"])
def get_image(image_id):
    user_id = get_optional_user_id()
    img = Image.query.get_or_404(image_id)
    return jsonify(image_to_dict(img, user_id))

@app.route("/images", methods=["POST"])
@creator_required
def add_image():
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        media_type = data.get("media_type", "image").strip().lower()
        upload_method = data.get("upload_method", "local").strip().lower()
    else:
        data = request.get_json(silent=True) or {}
        media_type = data.get("media_type", "image").strip().lower()
        upload_method = data.get("upload_method", "url").strip().lower()

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"message": "Title is required"}), 400
    if media_type not in ALLOWED_MEDIA_TYPES:
        return jsonify({"message": "Media type must be image or video"}), 400
    if upload_method not in {"local", "url"}:
        return jsonify({"message": "Upload method must be local or url"}), 400

    if upload_method == "local":
        media_url, error = save_uploaded_media(request.files.get("media_file"), media_type)
        if error:
            return jsonify({"message": error}), 400
    else:
        media_url = data.get("media_url") or data.get("image_url") or ""
        media_url = media_url.strip()
        if not media_url or not validate_media_url(media_url):
            return jsonify({"message": "A valid media URL is required"}), 400

    new_image = Image(
        title=title,
        caption=data.get("caption", "").strip(),
        location=data.get("location", "").strip(),
        people=data.get("people", "").strip(),
        image_url=media_url,
        media_type=media_type,
        upload_method=upload_method,
        user_id=request.user_id
    )
    db.session.add(new_image)
    db.session.commit()
    return jsonify({"message": "Media uploaded successfully", "id": new_image.id, "media_url": media_url}), 201

@app.route("/images/<int:image_id>", methods=["DELETE"])
@creator_required
def delete_image(image_id):
    img = Image.query.get_or_404(image_id)
    if img.user_id != request.user_id:
        return jsonify({"message": "Not authorized"}), 403
    db.session.delete(img)
    db.session.commit()
    return jsonify({"message": "Image deleted"})

@app.route("/images/search", methods=["GET"])
def search_images():
    user_id = get_optional_user_id()
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    images = Image.query.filter(
        Image.title.ilike(f"%{q}%") | Image.caption.ilike(f"%{q}%") |
        Image.location.ilike(f"%{q}%") | Image.people.ilike(f"%{q}%")
    ).order_by(Image.created_at.desc()).all()
    return jsonify([image_to_dict(img, user_id) for img in images])


# CREATOR STATS ENDPOINT (same)
@app.route("/images/<int:image_id>/stats", methods=["GET"])
@creator_required
def get_image_stats(image_id):
    img = Image.query.get_or_404(image_id)
    if img.user_id != request.user_id:
        return jsonify({"message": "You can only view stats for your own images"}), 403

    comments = Comment.query.filter_by(image_id=image_id).order_by(Comment.created_at.desc()).all()
    ratings = Rating.query.filter_by(image_id=image_id).all()
    reactions = Reaction.query.filter_by(image_id=image_id).order_by(Reaction.created_at.desc()).all()
    reaction_counts = {"like": 0, "happy": 0, "love": 0}
    for reaction in reactions:
        if reaction.reaction_type in reaction_counts:
            reaction_counts[reaction.reaction_type] += 1

    return jsonify({
        "image_id": image_id,
        "title": img.title,
        "image_url": img.image_url,
        "media_url": img.image_url,
        "media_type": getattr(img, "media_type", "image"),
        "upload_method": getattr(img, "upload_method", "url"),
        "avg_rating": round(sum(r.value for r in ratings)/len(ratings), 1) if ratings else 0,
        "rating_count": len(ratings),
        "ratings": [{"username": r.rater.username if r.rater else "Deleted", "value": r.value} for r in ratings],
        "reactions": [
            {
                "username": reaction.reactor.username if reaction.reactor else "Deleted",
                "reaction_type": reaction.reaction_type,
                "created_at": reaction.created_at.isoformat() if reaction.created_at else None,
            } for reaction in reactions
        ],
        "reaction_counts": reaction_counts,
        "comments": [{"username": c.author.username if c.author else "Anonymous", "text": c.text, "created_at": c.created_at.isoformat() if c.created_at else None} for c in comments]
    })


# COMMENT & RATING ROUTES (same as before)
@app.route("/comments/<int:image_id>", methods=["GET"])
def get_comments(image_id):
    comments = Comment.query.filter_by(image_id=image_id).order_by(Comment.created_at.desc()).all()
    return jsonify([{"id": c.id, "text": c.text, "username": c.author.username if c.author else "Anonymous", "created_at": c.created_at.isoformat() if c.created_at else None} for c in comments])

@app.route("/comments", methods=["POST"])
@token_required
def add_comment():
    data = request.json
    comment = Comment(image_id=data["image_id"], user_id=request.user_id, text=data["text"].strip())
    db.session.add(comment)
    db.session.commit()
    return jsonify({"message": "Comment added", "id": comment.id}), 201

@app.route("/ratings", methods=["POST"])
@token_required
def add_rating():
    data = request.json
    image_id = data["image_id"]
    value = int(data["value"])
    existing = Rating.query.filter_by(image_id=image_id, user_id=request.user_id).first()
    if existing:
        existing.value = value
    else:
        db.session.add(Rating(image_id=image_id, user_id=request.user_id, value=value))
    db.session.commit()
    return jsonify({"message": "Rating saved"}), 200


@app.route("/ratings/<int:image_id>", methods=["GET"])
def get_rating_summary(image_id):
    Image.query.get_or_404(image_id)
    ratings = Rating.query.filter_by(image_id=image_id).all()
    avg = round(sum(r.value for r in ratings) / len(ratings), 1) if ratings else 0
    return jsonify({"avg": avg, "count": len(ratings)})


@app.route("/reactions", methods=["POST"])
@token_required
def add_reaction():
    data = request.json or {}
    image_id = data.get("image_id")
    reaction_type = str(data.get("reaction_type", "")).strip().lower()
    allowed = {"like", "happy", "love"}

    if not image_id or reaction_type not in allowed:
        return jsonify({"message": "image_id and valid reaction_type are required"}), 400

    Image.query.get_or_404(image_id)
    existing = Reaction.query.filter_by(image_id=image_id, user_id=request.user_id).first()
    if existing:
        existing.reaction_type = reaction_type
    else:
        db.session.add(Reaction(image_id=image_id, user_id=request.user_id, reaction_type=reaction_type))
    db.session.commit()
    return jsonify({"message": "Reaction saved"}), 200


@app.route("/reactions/<int:image_id>", methods=["GET"])
def get_reactions(image_id):
    Image.query.get_or_404(image_id)
    counts = {"like": 0, "happy": 0, "love": 0}
    my_reaction = None
    user_id = get_optional_user_id()
    reactions = Reaction.query.filter_by(image_id=image_id).all()
    for reaction in reactions:
        if reaction.reaction_type in counts:
            counts[reaction.reaction_type] += 1
        if user_id and reaction.user_id == user_id:
            my_reaction = reaction.reaction_type
    return jsonify({"counts": counts, "my_reaction": my_reaction})


# USER MANAGEMENT — ONLY CREATOR
@app.route("/users", methods=["GET"])
@creator_required
def list_consumers():
    users = User.query.filter_by(role="consumer").order_by(User.created_at.desc()).all()
    return jsonify([{"id": u.id, "username": u.username, "created_at": u.created_at.isoformat() if u.created_at else None} for u in users])

@app.route("/users/<int:user_id>", methods=["DELETE"])
@creator_required
def delete_user(user_id):
    if request.user_id == user_id:
        return jsonify({"message": "Cannot delete yourself"}), 403
    user = User.query.get_or_404(user_id)
    if user.role == "creator":
        return jsonify({"message": "Cannot delete creator accounts"}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": f"User '{user.username}' deleted successfully"})



# SEED CREATOR
@app.route("/admin/seed-creator", methods=["POST"])
def seed_creator():
    # same as before
    pass   # (tumhara purana code yahan paste kar sakte ho)

def init_db():
    """Create tables and seed default creator (safe under multi-worker startup)."""
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("image")}
        if "media_type" not in columns:
            db.session.execute(text("ALTER TABLE image ADD COLUMN media_type VARCHAR(20) DEFAULT 'image' NOT NULL"))
        if "upload_method" not in columns:
            db.session.execute(text("ALTER TABLE image ADD COLUMN upload_method VARCHAR(20) DEFAULT 'url' NOT NULL"))
        db.session.commit()
        if User.query.filter_by(role="creator").first():
            return
        try:
            hashed = generate_password_hash("Mujeeb123")
            db.session.add(User(username="Admin Mujeeb", password=hashed, role="creator"))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
