import random
import logging
import time
from threading import Thread

from application.hashtagger import WAITING_INTERVAL, FAILURE_ALLOWANCE, comment_results, get_time


class HashtaggerCommenter(Thread):

    def __init__(self, name=None, api=None, user=None, user_output=None, sample_ids=None):
        super(HashtaggerCommenter, self).__init__()
        self.name = name
        self.api = api
        self.user = user
        self.user_output = user_output
        self.sample_ids = sample_ids

    def run(self):
        logging.info("HashtaggerCommenter %s@%s is running." % (self.getName(), get_time()))
        # All non-iterable variables will not be changed, so remove self. for quick access
        api = self.api
        user = self.user
        user_output = self.user_output
        sample_ids = self.sample_ids

        if api is None or user is None or user_output is None:
            return_dict = dict(api_none=(api is None), user_none=(user is None),
                               user_output=(user_output is None), sample_ids=(sample_ids is None))
            raise Exception("At least one of the required args is None. %s" % return_dict)
        # TODO: Add error checking for this empty list of message
        #         message = random.choice(user.message)

        #         if message.strip() == "":
        #             # Skip commenting if the message is empty
        #             comment_results[self.getName()] = (comment_success, len(sample_ids), failure)
        #             logging.info("HashtaggerCommenter %s@%s finished (no message)." %
        #                          (self.getName(), get_time()))
        #             return

        # Keep track of how many successful calls
        comment_success = 0
        # Maximum number of failures before stopping the call all
        failure = 0
        try:
            for ID in sample_ids:
                message = random.choice(user.message)
                is_commented = api.comment(mediaId=ID, commentText=message.strip())
                if is_commented:
                    comment_success += 1
                else:
                    try:
                        logging.error('Commenter %s@%s - Failure #%s - Failed to comment with (%s): %s | %s' %
                                      (self.getName(), get_time(), failure, message, api.LastJson['message'], ID))
                    except Exception as e:
                        # Probably something went wrong with api.LastJson
                        failure += 1
                        logging.error(e)
                        if failure >= FAILURE_ALLOWANCE['comment']:
                            user_output['fail_operation'] = True
                            break
                    else:
                        if api.LastResponse.status_code == 429:
                            failure += 1
                            logging.error('Commenter %s@%s - Failure #%s - Too many requests beyond the limit.' %
                                          (self.getName(), get_time(), failure))
                            # If the total failure is at maximum, we mark that this error causes us to fail
                            if failure >= FAILURE_ALLOWANCE['comment']:
                                user_output['exceed_limits'] = True
                                break
                        elif api.LastResponse.status_code == 400 and ('spam' in api.LastJson.keys()) and api.LastJson[
                            'spam']:
                            failure += 1
                            logging.error('Commenter %s@%s - Failure #%s - Spam filter has banned this.' %
                                          (self.getName(), get_time(), failure))
                            # If the total failure is at maximum, we mark that this error causes us to fail
                            if failure >= FAILURE_ALLOWANCE['comment']:
                                user_output['banned_comment'] = True
                                break
                    finally:
                        # Sleep then continue
                        time.sleep(WAITING_INTERVAL)
        except Exception as e:
            # Something went wrong inside the for loop that causes us to fail
            user_output['fail_operation'] = True
            logging.error(e)
        finally:
            # Make sure that the result is in there despite any operational issues
            comment_results[self.getName()] = (comment_success, len(sample_ids), failure)
            logging.info("HastaggerCommenter %s@%s is finished." % (self.getName(), get_time()))
