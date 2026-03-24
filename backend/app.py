from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from models import db, Image, Comment, Rating, User
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
CORS(app, resources={r"/*": {"origins": "*"}})


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


# HEALTH
@app.route("/")
def home():
    return jsonify({"message": "PixShare API Running ✨"})


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
def image_to_dict(img):
    ratings = [r.value for r in img.ratings]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    return {
        "id": img.id, "title": img.title, "caption": img.caption,
        "location": img.location, "people": img.people, "image_url": img.image_url,
        "created_at": img.created_at.isoformat() if img.created_at else None,
        "uploader": img.uploader.username if img.uploader else "Unknown",
        "avg_rating": avg_rating, "rating_count": len(ratings), "comment_count": len(img.comments)
    }

@app.route("/images", methods=["GET"])
def get_images():
    images = Image.query.order_by(Image.created_at.desc()).all()
    return jsonify([image_to_dict(img) for img in images])

@app.route("/images/<int:image_id>", methods=["GET"])
def get_image(image_id):
    img = Image.query.get_or_404(image_id)
    return jsonify(image_to_dict(img))

@app.route("/images", methods=["POST"])
@creator_required
def add_image():
    data = request.json
    if not data.get("title") or not data.get("image_url"):
        return jsonify({"message": "Title and image URL are required"}), 400
    new_image = Image(**{k: data.get(k) for k in ["title","caption","location","people","image_url"]}, user_id=request.user_id)
    db.session.add(new_image)
    db.session.commit()
    return jsonify({"message": "Image uploaded successfully", "id": new_image.id}), 201

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
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    images = Image.query.filter(
        Image.title.ilike(f"%{q}%") | Image.caption.ilike(f"%{q}%") |
        Image.location.ilike(f"%{q}%") | Image.people.ilike(f"%{q}%")
    ).order_by(Image.created_at.desc()).all()
    return jsonify([image_to_dict(img) for img in images])


# CREATOR STATS ENDPOINT (same)
@app.route("/images/<int:image_id>/stats", methods=["GET"])
@creator_required
def get_image_stats(image_id):
    img = Image.query.get_or_404(image_id)
    if img.user_id != request.user_id:
        return jsonify({"message": "You can only view stats for your own images"}), 403

    comments = Comment.query.filter_by(image_id=image_id).order_by(Comment.created_at.desc()).all()
    ratings = Rating.query.filter_by(image_id=image_id).all()

    return jsonify({
        "image_id": image_id,
        "title": img.title,
        "image_url": img.image_url,
        "avg_rating": round(sum(r.value for r in ratings)/len(ratings), 1) if ratings else 0,
        "rating_count": len(ratings),
        "ratings": [{"username": r.rater.username if r.rater else "Deleted", "value": r.value} for r in ratings],
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role="creator").first():
            hashed = generate_password_hash("Mujeeb123")
            db.session.add(User(username="Admin Mujeeb", password=hashed, role="creator"))
            db.session.commit()
            print("✅ Default creator seeded")
    app.run(host="0.0.0.0", debug=True, port=5000)







    