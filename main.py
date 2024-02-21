from flask import Flask

from controller import flask_controller as googlesheets_controller

app = Flask(__name__)
app.register_blueprint(googlesheets_controller)


@app.route('/')
def home():
    return ''


if __name__ == '__main__':
    app.run()
