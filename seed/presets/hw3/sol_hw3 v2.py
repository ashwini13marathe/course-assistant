"""CS 201 HW3 reference solution: binary search tree."""


class _Node:
    __slots__ = ("key", "left", "right")

    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None
        self._size = 0

    def __len__(self):
        return self._size

    def insert(self, key):
        def _insert(node):
            if node is None:
                self._size += 1
                return _Node(key)
            if key < node.key:
                node.left = _insert(node.left)
            elif key > node.key:
                node.right = _insert(node.right)
            return node
        self.root = _insert(self.root)

    def contains(self, key):
        node = self.root
        while node:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def delete(self, key):
        def _delete(node, key):
            if node is None:
                raise KeyError(key)
            if key < node.key:
                node.left = _delete(node.left, key)
            elif key > node.key:
                node.right = _delete(node.right, key)
            else:
                if node.left is None:
                    return node.right
                if node.right is None:
                    return node.left
                succ = node.right
                while succ.left:
                    succ = succ.left
                node.key = succ.key
                node.right = _delete(node.right, succ.key)
            return node
        self.root = _delete(self.root, key)
        self._size -= 1

    def inorder(self):
        out = []

        def walk(node):
            if node:
                walk(node.left)
                out.append(node.key)
                walk(node.right)
        walk(self.root)
        return out

    def height(self):
        def h(node):
            return -1 if node is None else 1 + max(h(node.left), h(node.right))
        return h(self.root)
