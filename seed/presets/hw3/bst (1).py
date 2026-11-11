"""CS 201 HW3: binary search tree. Fill in every method marked TODO.

Keep this file name (bst.py) so the autograder can import it.
"""


class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None
        self.size = 0

    def __len__(self):
        raise NotImplementedError  # TODO: O(1)

    def insert(self, key):
        raise NotImplementedError  # TODO: duplicates are ignored

    def contains(self, key):
        raise NotImplementedError  # TODO

    def delete(self, key):
        raise NotImplementedError  # TODO: leaf, one child, two children; KeyError if missing

    def inorder(self):
        raise NotImplementedError  # TODO: sorted list of keys

    def height(self):
        raise NotImplementedError  # TODO: -1 for an empty tree, 0 for one node
