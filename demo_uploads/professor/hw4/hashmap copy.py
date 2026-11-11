"""CS 201 HW4: hash map with separate chaining. Fill in every method marked TODO."""


class HashMap:
    INITIAL_BUCKETS = 8
    MAX_LOAD = 0.75

    def __init__(self):
        self._buckets = [[] for _ in range(self.INITIAL_BUCKETS)]
        self._size = 0

    def _index(self, key):
        raise NotImplementedError  # TODO

    def put(self, key, value):
        raise NotImplementedError  # TODO: resize first if the load factor would pass MAX_LOAD

    def get(self, key):
        raise NotImplementedError  # TODO

    def remove(self, key):
        raise NotImplementedError  # TODO

    def __len__(self):
        raise NotImplementedError  # TODO

    def __contains__(self, key):
        raise NotImplementedError  # TODO

    def keys(self):
        raise NotImplementedError  # TODO

    def _resize(self):
        raise NotImplementedError  # TODO: double the buckets and rehash
