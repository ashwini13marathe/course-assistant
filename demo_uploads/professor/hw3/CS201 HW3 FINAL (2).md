# CS 201, HW3: Binary search trees

Implement a binary search tree of integers in `hw3/bst.py`.

## Requirements

1. `BST.insert(key)` adds a key; inserting a key that's already present does nothing.
2. `BST.contains(key)` returns True or False.
3. `BST.delete(key)` removes a key and handles all three cases: a leaf, a node with one child, and a node with two children. Deleting a missing key raises `KeyError`.
4. `BST.inorder()` returns the keys as a sorted list.
5. `BST.height()` returns the height; an empty tree has height -1 and a single node has height 0.
6. `len(tree)` returns the number of keys in O(1) time.
7. Every operation except `inorder` and `height` must run in O(h) time, where h is the tree's height.

## Notes

- Use your own node class; don't store keys in a Python list or dict.
- Test deletion of the root in all three cases.
