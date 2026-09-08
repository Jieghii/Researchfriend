from routes.auth import bp as auth_bp
from routes.chat import bp as chat_bp
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
