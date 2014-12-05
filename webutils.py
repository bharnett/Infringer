import json


class AjaxResponse(object):
    def __init__(self, message):
        self.status = 'success'
        self.message = message

    def to_JSON(self):
        return json.dumps(self.__dict__)
