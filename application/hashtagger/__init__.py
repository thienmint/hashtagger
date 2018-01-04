from application.InstagramAPI import InstagramAPI

from pony.orm import *

import random
import logging
import time

# Number of Instagram post to like/comment per hour interval
POST_LIMIT = 25
# 8s interval between each comment posting and/or exceeding_limit count
WAITING_INTERVAL = 30
# FAILURE_ALLOWANCE: how many number of failures before it halts failing liking/commenting thread overall
FAILURE_ALLOWANCE = dict(like=10, comment=10)
# Like_threads: keep a list of all the HashtaggerLiker threads created
# Like_results: keep the results for each thread that is liking posts
like_threads = dict()
like_results = dict()
# comment_threads: keep a list of all the HashtaggerCommenter threads created
# comment_results: keep the results for each thread that is commenting posts
comment_threads = dict()
comment_results = dict()


def get_time():
    return time.strftime("%H:%M - %m/%d/%y")


def generate_history(username, message="", comment_success=0, like_success=0, total=0, user_db=None):
    if user_db is None:
        logging.warning("No user_db given")
    else:
        with db_session:
            user = user_db.get(username=username)
            user.history['info'].append(
                {
                    'time_completion': get_time(),
                    'comment_success': comment_success,
                    'like_success': like_success,
                    'total': total,
                    'message': message
                })
            logging.info("Updated history for %s" % username)
        logging.info('%s: %s | comment = %s | like = %s | total = %s' %
              (username, message, comment_success, like_success, total))


from application.hashtagger.HashtaggerLiker import HashtaggerLiker
from application.hashtagger.HashtaggerCommenter import HashtaggerCommenter


def start_process(users, user_db):
    post_return = dict()
    api_lookup = dict()
    for user in users:
        # Instantiate all the codes to return
        user_output = dict(fail_login=False, fail_feed=False, fail_operational=False, banned_comment=False,
                           exceed_limits=False, completed=False)
        post_return[user.username] = user_output

        api = InstagramAPI(user.username, user.password)

        # Verify that login is success
        api.login()
        if not api.isLoggedIn:
            user_output['fail_login'] = True
            generate_history(user.username, message="Problem loging into the account", user_db=user_db)
            # Skip the user who fails to login
            continue

        api_lookup[user.username] = api
        got_feed = api.getHashtagFeed(user.hashtag.lstrip('#'))

        # Verify that we successfully get the feed, otherwise skip this user
        if not got_feed:
            # skip this user, unable to get the feed
            user_output['fail_feed'] = True
            generate_history(user.username, message="Failed to get the tags feed list for user.", user_db=user_db)
            continue

        # If this operation fails, we simply skip the user as well. This could be because
        # LastJson doesn't have the required keys or data structure. Check with the API again.
        try:
            sample_ids = [item['pk'] for item in random.sample(api.LastJson['items'], POST_LIMIT)]
        except Exception as e:
            user_output['fail_operation'] = True
            logging.error(e)
            generate_history(user.username, message="Operational failure: %s" % e, user_db=user_db)
            continue
        else:
            # Call another function that like/comment the posts
            like_threads[user.username] = HashtaggerLiker(name=user.username, api=api, user=user,
                                                          user_output=user_output, sample_ids=sample_ids)
            try:
                like_threads[user.username].start()
            except Exception as e:
                logging.error(e)

            comment_threads[user.username] = HashtaggerCommenter(name=user.username, api=api, user=user,
                                                                 user_output=user_output, sample_ids=sample_ids)
            try:
                comment_threads[user.username].start()
            except Exception as e:
                logging.error(e)

            logging.info('Started process to like/comment {0} items for {1}'.format(len(sample_ids), user.username))
    for user in users:
        username = user.username

        # If the api wasn't generated/login, just skip this user
        if username not in api_lookup:
            continue
        # Add check to make sure username is in the list
        if username in like_threads:
            like_t = like_threads[username]
            like_t.join()
            del like_threads[username]

        if username in comment_threads:
            comment_t = comment_threads[username]
            comment_t.join()

            del comment_threads[username]

        like_result = like_results[username] if username in like_results else None
        comment_result = comment_results[username] if username in comment_results else None

        generate_history(username, "Completed.",
                         like_success=like_result[0] if like_result is not None else 0,
                         comment_success=comment_result[0] if comment_result is not None else 0,
                         total=POST_LIMIT, user_db=user_db
                         )
        api_lookup[username].logout()
    return post_return
