import logging
import time
from threading import Thread

from application.hashtagger import WAITING_INTERVAL, FAILURE_ALLOWANCE, like_results, get_time


class HashtaggerLiker(Thread):

    def __init__(self, name=None, api=None, user=None, user_output=None, sample_ids=None):
        super(HashtaggerLiker, self).__init__()
        self.name = name
        self.api = api
        self.user = user
        self.user_output = user_output
        self.sample_ids = sample_ids

    def run(self):
        logging.info("HashtaggerLiker %s@%s is running." % (self.getName(), get_time()))
        # All non-iterable variables will not be changed, so remove self. for quick access
        api = self.api
        user = self.user
        user_output = self.user_output
        sample_ids = self.sample_ids

        if api is None or user is None or user_output is None:
            return_dict = dict(api_none=(api is None), user_none=(user is None),
                               user_output=(user_output is None), sample_ids=(sample_ids is None))
            raise Exception("At least one of the required args is None. %s" % return_dict)

        # Keep track of how many successful calls
        like_success = 0
        # Maximum number of failures before stopping the call all
        failure = 0
        try:
            for ID in sample_ids:
                is_liked = api.like(mediaId=ID)
                if is_liked:
                    like_success += 1
                else:
                    failure += 1
                    try:
                        logging.error('Liker %s@%s - Failure #%s - Failed to like: %s' %
                                      (self.getName(), get_time(), failure, api.LastJson['message']))
                    except Exception as e:
                        # Probably something went wrong with api.LastJson
                        failure += 1
                        logging.error(e)
                        if failure >= FAILURE_ALLOWANCE['like']:
                            user_output['fail_operation'] = True
                            break
                    else:
                        if api.LastResponse.status_code == 429:
                            logging.error('Liker %s@%s - Failure #%s - Too many requests beyond the limit.' %
                                          (self.getName(), get_time(), failure))
                    finally:
                        # If the total failure is at maximum, we mark that this error causes us to fail
                        if failure >= FAILURE_ALLOWANCE['like']:
                            user_output['exceed_limits'] = True
                            break
                        else:
                            # Sleep then continue
                            time.sleep(WAITING_INTERVAL)
        except Exception as e:
            # Something went wrong inside the for loop that causes us to fail
            user_output['fail_operation'] = True
            logging.error(e)
        finally:
            # Make sure that the result is in there despite any operational issues
            like_results[self.getName()] = (like_success, len(sample_ids), failure)
            logging.info("HashtaggerLiker %s@%s is finished." % (self.getName(), get_time()))
