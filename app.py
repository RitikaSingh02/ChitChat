# from flask import jsonify
# import json
from forms import LoginForm, RegistrationForm
from models import User
from flask_socketio import SocketIO, send, join_room, leave_room
import hashlib
import base64
from flask import Flask, render_template, redirect, flash, request, make_response
from flask.helpers import url_for
from flask_sqlalchemy import SQLAlchemy

from dotenv import load_dotenv
import os
import bcrypt
import time

from flask_login import LoginManager, login_user, logout_user, current_user, login_required

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize login manager
login = LoginManager(app)
login.init_app(app)  # configuring the app for Flask-Login

# Flask-Login uses sessions for authentication (default) so setting the secret key
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800


@login.user_loader
def load_user(user_id):
    return User.query.get(user_id)
# It should return None (not raise an exception) if the ID is not valid.


socketio = SocketIO(app, manage_session=False,
                    cors_allowed_origins='*')
# managed_session = False (as we want that the change in session from
# the  socketio side should reflect in http and vise versa)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html')


@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html')


@app.route("/", methods=['GET', 'POST'])
def index():

    reg_form = RegistrationForm()

    # Update database if validation success
    if reg_form.validate_on_submit():
        username = reg_form.username.data
        password = reg_form.password.data
        pass_bytes = password.encode("ascii")
        base64_bytes = base64.b64encode(pass_bytes)
        hashed = bcrypt.hashpw(
            base64.b64encode(hashlib.sha256(base64_bytes).digest()),
            bcrypt.gensalt()
        )
        # Add username & hashed password to DB

        user = User(username=username, password=hashed)
        db.session.add(user)
        db.session.commit()

        flash('Registered successfully. Please login.', 'success')
        return redirect(url_for('login'))

    return render_template("index.html", form=reg_form)


@app.route("/login", methods=['GET', 'POST'])
def login():

    login_form = LoginForm()

    # Allow login if validation success
    if login_form.validate_on_submit():
        user_object = User.query.filter_by(
            username=login_form.username.data).first()
        login_user(user_object)
        return redirect(url_for('chat'))

    return render_template("login.html", form=login_form)

# def _build_cors_prelight_response():
#     response = make_response()
#     response.headers.add("Access-Control-Allow-Origin", "*")
#     response.headers.add('Access-Control-Allow-Headers', "*")
#     response.headers.add('Access-Control-Allow-Methods', "*")
#     return response


# def _corsify_actual_response(response):
#     response.headers.add("Access-Control-Allow-Origin", "*")
#     return response


# @app.route('/login', methods=['POST', 'OPTIONS'])
# def login():
#     # print(request)
#     if request.method == "OPTIONS":  # CORS preflight
#         return _build_cors_prelight_response()
#     else:
#         print(request.get_json(force=True))
#         data = request.get_json(force=True)
#         uname = data["username"]
#         password = data["password"]
#         res = {}
#         user_object = User.query.filter_by(username=uname,
#                                            password=password).first()
#         if User.query.filter_by(username=uname).first() is None:
#             user = User(username=uname, password=password)
#             db.session.add(user)
#             db.session.commit()
#             login_user(user)
#             res['msg'] = "login success"
#             return _corsify_actual_response(jsonify(res)), 200
#         elif user_object is None:
#             res['msg'] = "Invalid credentials"
#             return _corsify_actual_response(jsonify(res)), 401
#         else:
#             # session['user'] = uname
#             login_user(user_object)
#             # print(current_user.username)
#             res['msg'] = "login success redirect to the url of the home page"
#             return _corsify_actual_response(jsonify(res)), 200


@app.route("/logout", methods=['GET'])
@login_required
def logout():

    # Logout user
    logout_user()
    login_form = LoginForm()

    flash('You have logged out successfully', 'success')
    return render_template("login.html", form=login_form)

# @app.route("/logout", methods=['GET', 'OPTIONS'])
# @login_required
# def logout():

#     # Logout user
#     if request.method == "OPTIONS":  # CORS preflight
#         return _build_cors_prelight_response()
#     else:
#         logout_user()
#         # flash('You have logged out successfully', 'success')
#         res = {"msg": "logout success"}
#         return _corsify_actual_response(jsonify(res)), 200


# Predefined rooms for chat
ROOMS = ["Landing", "News", "Games", "Coding"]


@app.route("/chat", methods=['GET'])
def chat():
    if not current_user.is_authenticated:
        flash('Please login', 'danger')
        return redirect(url_for('login'))
    # authenticated!!
    return render_template("chat.html", username=current_user.username, rooms=ROOMS)


# @app.route("/music", methods=['GET'])
# def music():
#     if not current_user.is_authenticated:
#         flash('Please login', 'danger')
#         return redirect(url_for('login'))
#     """authenticated!!"""
#     return render_template("music.html")


###################################SOCKETIO##########################################################

@socketio.on('user-msg')
def on_message(data):
    # Broadcast messages
    msg = data["msg"]
    username = data["username"]
    room = data["room"]
    time_stamp = time.strftime('%b-%d %I:%M%p', time.localtime())
    # print("incoming msgs triggered")
    send({"username": username, "msg": msg, "time_stamp": time_stamp}, room=room)


@socketio.on('join-room')
def room_join(data):
    # User joins a room

    username = data["username"]
    room = data["room"]
    join_room(room)

    # Broadcast that new user has joined
    send({"msg": username + " has joined the " + room + " room."}, room=room)


@socketio.on('leave')
def on_leave(data):
    # User leaves a room

    username = data['username']
    room = data['room']
    leave_room(room)
    send({"msg": username + " has left the room"}, room=room)


if __name__ == "__main__":
    app.run(debug=True)
