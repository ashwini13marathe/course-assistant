# CS 201, HW4: Hash maps

Implement a hash map with separate chaining in `hw4/hashmap.py`. Starter code is in your branch.

## Requirements

1. `put(key, value)` inserts or replaces a value.
2. `get(key)` returns the value, or raises `KeyError` if the key is missing.
3. `remove(key)` deletes a key and returns its value; raises `KeyError` if missing.
4. `len(m)` returns the number of keys in O(1) time; `key in m` works.
5. Each bucket is a Python list of `(key, value)` pairs (separate chaining). Start with 8 buckets.
6. When the load factor (keys / buckets) would go above 0.75, double the number of buckets and rehash every key.
7. `keys()` returns all keys, in any order.
8. Average-case `put`, `get` and `remove` must be O(1).

## Notes

- Use Python's built-in `hash()`; don't use a `dict` or `set` anywhere in your class.
- Write a short comment explaining why resizing keeps `put` amortized O(1).
