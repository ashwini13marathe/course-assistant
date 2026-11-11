"""CS 201 HW3, alice: binary search tree."""


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
        return self.size

    def insert(self, key):
        if self.root is None:
            self.root = Node(key)
            self.size += 1
            return
        node = self.root
        while True:
            if key < node.key:
                if node.left is None:
                    node.left = Node(key)
                    break
                node = node.left
            else:
                if node.right is None:
                    node.right = Node(key)
                    break
                node = node.right
        self.size += 1

    def contains(self, key):
        node = self.root
        while node:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def delete(self, key):
        parent, node = None, self.root
        while node and node.key != key:
            parent, node = node, (node.left if key < node.key else node.right)
        if node is None:
            raise KeyError(key)
        if node.left and node.right:
            succ = node.right
            while succ.left:
                succ = succ.left
            node.key = succ.key
            return
        child = node.left or node.right
        if parent is None:
            self.root = child
        elif parent.left is node:
            parent.left = child
        else:
            parent.right = child
        self.size -= 1

    def inorder(self):
        out = []

        def walk(n):
            if n:
                walk(n.left)
                out.append(n.key)
                walk(n.right)
        walk(self.root)
        return out

    def height(self):
        def h(n):
            return 0 if n is None else 1 + max(h(n.left), h(n.right))
        return h(self.root)
