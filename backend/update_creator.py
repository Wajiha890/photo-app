from app import app, db, User
from werkzeug.security import generate_password_hash

# Use the app's context
with app.app_context():
    creator = User.query.filter_by(role="creator").first()
    if creator:
        creator.username = "Admin Mujeeb"
        creator.password = generate_password_hash("Mujeeb123")
        db.session.commit()
        print("✅ Creator updated successfully")
    else:
        print("⚠️ No creator found in the database")