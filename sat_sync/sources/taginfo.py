import json


class TaginfoSource:

    def __init__(self, filename=None):
        self.filename = filename

    def identifiers(self):

        if self.filename is None:
            return set()

        with open(self.filename) as f:
            data = json.load(f)

        return {item["value"] for item in data}