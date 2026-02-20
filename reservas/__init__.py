from flask import Flask


def create_app(config_name=None):
    app = Flask(__name__)
    if config_name:
        app.config.from_object(config_name)
    else:
        app.config['DEBUG'] = True
        app.config['SECRET_KEY'] = 'reservas-secret-key'
    return app
