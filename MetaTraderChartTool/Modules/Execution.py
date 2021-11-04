

from pandas import to_datetime
from time import sleep
from datetime import datetime


class Execution:

    def __init__(self, _zmq):
        self._zmq = _zmq

    ##########################################################################

    def execute(self,
                  params,
                  _delay=0.01,
                  _wbreak=10,
                  _type="DRAW"):

        _check = ''

        # Reset thread Data output
        self._zmq._set_response_(None)

        # Draw
        print(f"Request {datetime.now()}")
        if _type == "DRAW":
            self._zmq.send_draw_request(params)
        elif _type == "DELETE":
            self._zmq.send_delete_request(params)

        # While loop start time reference
        _ws = to_datetime('now')

        # While Data not received, sleep until timeout
        while self._zmq._valid_response_('zmq') == False:
            sleep(_delay)

            if (to_datetime('now') - _ws).total_seconds() > (_delay * _wbreak):
                break
        print(f"Response {datetime.now()}")

        # If Data received, return DataFrame
        if self._zmq._valid_response_('zmq'):

            response = self._zmq._get_response_()
            if _check in response.keys():
                return response

        # Default
        return None

    ##########################################################################
