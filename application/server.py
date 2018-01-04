from flask import Flask, render_template, request, jsonify
from flask_apscheduler import APScheduler
from application.InstagramAPI import InstagramAPI

from application.models import *

import threading
import logging
import webbrowser
from datetime import datetime

# Code logic here
from application.hashtagger import start_process

# Setting logger to INFO level
root = logging.getLogger()
root.setLevel(logging.INFO)

app = Flask(__name__, static_url_path='/static')

app.config.from_object(__name__)
app.config.update(dict(
    SECRET_KEY='development key'
))
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SCHEDULER_API_ENABLED'] = True
# Keeping a list of job (should be only 1)
jobs = []


def run_process():
    users = []
    with db_session:
        users.append(select(u for u in User)[:])

    start_process(users[0], User)


@app.route('/')
def main():
    with db_session:
        users = select(u for u in User)[:]
        return render_template('main.html', users=users)


@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    # Filter out all empty messages and leading/trailing spaces
    comments = [comment for comment in data['comment'] if comment.strip() != ""]

    try:
        with db_session:
            User(username=data["username"].strip(), password=data["password"], hashtag=data["hashtag"].lstrip('#'), message=comments,
                 verified=False, history=dict(info=list()))
    except Exception:
        return jsonify("Username already exists!")

    return jsonify("User has been stored to db successfully!")


@app.route('/remove_user', methods=["POST"])
def remove_user():
    data = request.get_json()
    with db_session:
        User.get(username=data['username']).delete()

    return jsonify("User " + data["username"] + " has been removed")


@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()

    with db_session:
        user = User.get(username=data['username'])

        try:
            api = InstagramAPI(user.username, user.password)
            api.login()
            # api.getv2Inbox()

            if api.isLoggedIn:
                user.verified = True

            api.logout()

        except Exception:
            return jsonify(400)

    return jsonify(200)


@app.route('/edit', methods=["POST"])
def edit():
    data = request.get_json()
    print(data)
    with db_session:
        try:
            user = User.get(username=data['username'])
            if ('hashtag' in data) and (data['hashtag'].lstrip('#') != ""):
                user.hashtag = data['hashtag']
            if ('comment' in data) and (len(data['comment']) > 0):
                user.message = data['comment']
        except Exception as e:
            return jsonify('Failed to edit: %s' % e)

    return jsonify("User " + data["username"] + " has been successfully edited!")


@app.route('/<username>')
def history(username):
    with db_session:
        user = User.get(username=username)
        return render_template('history.html', username=username,
                               verified=user.verified, history=user.history['info'])


@app.route('/next_run_time', methods=['POST'])
def next_run_time():
    try:
        next_run = jobs[0].next_run_time
        now = datetime.now(tz=next_run.tzinfo)
        diff = round((now - next_run).total_seconds())
        if diff < 0:
            return jsonify(dict(minutes=int((diff*-1) / 60), seconds=round((diff*-1) % 60)))
        elif diff == 0:
            return jsonify(dict(minutes=0, seconds=0))
        else:
            return jsonify(dict(minutes=int(diff / 60), seconds=round(diff % 60)))
    except Exception as e:
        logging.warning(e)
        return jsonify(dict(minutes=-1, seconds=-1))


# Make a scheduler
scheduler = APScheduler()
jobs.append(scheduler.scheduler.add_job(run_process, 'interval', minutes=60,
                                        name='like_comment_job', max_instances=1, coalesce=True))
scheduler.init_app(app)
logging.info("Going to start the application now!")
scheduler.start()

if __name__ == '__main__':
    threading.Timer(3, lambda: webbrowser.open(url='http://localhost:5000/')).start()
    app.run(host="127.0.0.1", port=5000, threaded=True, debug=False)
