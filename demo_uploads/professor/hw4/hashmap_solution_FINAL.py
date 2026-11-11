"""CS 201 HW4 reference solution: hash map with separate chaining."""


class HashMap:
    INITIAL_BUCKETS = 8
    MAX_LOAD = 0.75

    def __init__(self):
        self._buckets = [[] for _ in range(self.INITIAL_BUCKETS)]
        self._size = 0

    def _index(self, key):
        return hash(key) % len(self._buckets)

    def put(self, key, value):
        bucket = self._buckets[self._index(key)]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        # Doubling at a fixed load factor means each key is rehashed O(1) times
        # on average, so put stays amortized O(1).
        if (self._size + 1) / len(self._buckets) > self.MAX_LOAD:
            self._resize()
            bucket = self._buckets[self._index(key)]
        bucket.append((key, value))
        self._size += 1

    def get(self, key):
        for k, v in self._buckets[self._index(key)]:
            if k == key:
                return v
        raise KeyError(key)

    def remove(self, key):
        bucket = self._buckets[self._index(key)]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                del bucket[i]
                self._size -= 1
                return v
        raise KeyError(key)

    def __len__(self):
        return self._size

    def __contains__(self, key):
        try:
            self.get(key)
            return True
        except KeyError:
            return False

    def keys(self):
        return [k for bucket in self._buckets for k, _ in bucket]

    def _resize(self):
        old = self._buckets
        self._buckets = [[] for _ in range(len(old) * 2)]
        for bucket in old:
            for k, v in bucket:
                self._buckets[self._index(k)].append((k, v))
