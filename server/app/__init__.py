import os
from flask import Flask, jsonify
from .db import close_db, init_db

def create_app(test_config=None):
    app=Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY','change-me'),
        DATABASE=os.environ.get('DATABASE',os.path.join(app.instance_path,'homebuster.sqlite3')),
        PASSWORD_MIN_LENGTH=int(os.environ.get('PASSWORD_MIN_LENGTH','8')),
        TMDB_API_KEY=os.environ.get('TMDB_API_KEY',''),
        UPCITEMDB_API_KEY=os.environ.get('UPCITEMDB_API_KEY',''),
        UPCITEMDB_FREE_ENABLED=os.environ.get('UPCITEMDB_FREE_ENABLED','false').lower() in ('1','true','yes','on'),
        BARCODE_LOOKUP_URL=os.environ.get('BARCODE_LOOKUP_URL',''),
    )
    if test_config: app.config.update(test_config)
    app.teardown_appcontext(close_db)
    with app.app_context(): init_db()
    from .mobile_api import bp as mobile_bp
    app.register_blueprint(mobile_bp)
    @app.get('/')
    def root():
        return jsonify({'name':'Homebuster','message':'Homebuster server is running','mobile_api':'/api/v1/health'})
    return app
