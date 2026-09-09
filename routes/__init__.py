from routes.admin import bp as admin_bp
from routes.auth import bp as auth_bp
from routes.chat import bp as chat_bp
from routes.discover import bp as discover_bp
from routes.feedback import bp as feedback_bp
from routes.glass import bp as glass_bp
from routes.invite import bp as invite_bp
from routes.match import bp as match_bp
from routes.profile import bp as profile_bp
from routes.thoughts import bp as thoughts_bp
from routes.topics import bp as topics_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(match_bp)
    app.register_blueprint(topics_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(thoughts_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(discover_bp)
    app.register_blueprint(glass_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(invite_bp)
    app.register_blueprint(admin_bp)
