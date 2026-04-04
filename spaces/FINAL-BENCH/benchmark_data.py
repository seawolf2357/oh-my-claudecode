"""
Coding benchmark problems with test cases for Kimi K2.5 evaluation.
Each problem has: id, title, category, difficulty, prompt, test code, reference solution.
"""

PROBLEMS = [
    {
        "id": "P01",
        "title": "Two Sum",
        "category": "Array",
        "difficulty": "Easy",
        "prompt": """Write a Python function `two_sum(nums: list[int], target: int) -> list[int]` that returns indices of the two numbers that add up to target. Each input has exactly one solution. Do not use the same element twice. Return the answer as a list of two indices.""",
        "test_code": """
assert sorted(two_sum([2,7,11,15], 9)) == [0,1]
assert sorted(two_sum([3,2,4], 6)) == [1,2]
assert sorted(two_sum([3,3], 6)) == [0,1]
assert sorted(two_sum([1,5,3,7], 8)) == [1,3]
assert sorted(two_sum([-1,0,1,2], 1)) == [0,2]
""",
    },
    {
        "id": "P02",
        "title": "Valid Parentheses",
        "category": "Stack",
        "difficulty": "Easy",
        "prompt": """Write a Python function `is_valid(s: str) -> bool` that determines if the input string of brackets '(){}[]' is valid. Valid means every open bracket is closed by the same type in the correct order.""",
        "test_code": """
assert is_valid("()") == True
assert is_valid("()[]{}") == True
assert is_valid("(]") == False
assert is_valid("([)]") == False
assert is_valid("{[]}") == True
assert is_valid("") == True
assert is_valid("((") == False
""",
    },
    {
        "id": "P03",
        "title": "Fibonacci Sequence",
        "category": "Dynamic Programming",
        "difficulty": "Easy",
        "prompt": """Write a Python function `fib(n: int) -> int` that returns the nth Fibonacci number. fib(0)=0, fib(1)=1, fib(2)=1, fib(3)=2, etc.""",
        "test_code": """
assert fib(0) == 0
assert fib(1) == 1
assert fib(2) == 1
assert fib(10) == 55
assert fib(20) == 6765
assert fib(30) == 832040
""",
    },
    {
        "id": "P04",
        "title": "Reverse Linked List",
        "category": "Linked List",
        "difficulty": "Easy",
        "prompt": """Write Python code with a class `ListNode` with attributes `val` and `next`, and a function `reverse_list(head: ListNode) -> ListNode` that reverses a singly linked list and returns the new head. If head is None, return None.""",
        "test_code": """
def build(vals):
    if not vals: return None
    head = ListNode(vals[0])
    cur = head
    for v in vals[1:]:
        cur.next = ListNode(v)
        cur = cur.next
    return head
def to_list(head):
    r = []
    while head:
        r.append(head.val)
        head = head.next
    return r
assert to_list(reverse_list(build([1,2,3,4,5]))) == [5,4,3,2,1]
assert to_list(reverse_list(build([1,2]))) == [2,1]
assert reverse_list(None) is None
assert to_list(reverse_list(build([1]))) == [1]
""",
    },
    {
        "id": "P05",
        "title": "Binary Search",
        "category": "Search",
        "difficulty": "Easy",
        "prompt": """Write a Python function `binary_search(nums: list[int], target: int) -> int` that returns the index of target in a sorted array nums. If not found, return -1.""",
        "test_code": """
assert binary_search([-1,0,3,5,9,12], 9) == 4
assert binary_search([-1,0,3,5,9,12], 2) == -1
assert binary_search([5], 5) == 0
assert binary_search([1,2,3,4,5], 1) == 0
assert binary_search([1,2,3,4,5], 5) == 4
assert binary_search([], 3) == -1
""",
    },
    {
        "id": "P06",
        "title": "Merge Sorted Arrays",
        "category": "Array",
        "difficulty": "Medium",
        "prompt": """Write a Python function `merge_sorted(arr1: list[int], arr2: list[int]) -> list[int]` that merges two sorted arrays into one sorted array.""",
        "test_code": """
assert merge_sorted([1,3,5], [2,4,6]) == [1,2,3,4,5,6]
assert merge_sorted([], [1,2,3]) == [1,2,3]
assert merge_sorted([1,2,3], []) == [1,2,3]
assert merge_sorted([1,1,1], [1,1,1]) == [1,1,1,1,1,1]
assert merge_sorted([-5,0,3], [-3,1,4]) == [-5,-3,0,1,3,4]
""",
    },
    {
        "id": "P07",
        "title": "Longest Common Prefix",
        "category": "String",
        "difficulty": "Easy",
        "prompt": """Write a Python function `longest_common_prefix(strs: list[str]) -> str` that finds the longest common prefix among a list of strings. If no common prefix, return empty string.""",
        "test_code": """
assert longest_common_prefix(["flower","flow","flight"]) == "fl"
assert longest_common_prefix(["dog","racecar","car"]) == ""
assert longest_common_prefix(["abc","abc","abc"]) == "abc"
assert longest_common_prefix(["a"]) == "a"
assert longest_common_prefix([""]) == ""
assert longest_common_prefix(["prefix","pre","predict"]) == "pre"
""",
    },
    {
        "id": "P08",
        "title": "Maximum Subarray (Kadane's)",
        "category": "Dynamic Programming",
        "difficulty": "Medium",
        "prompt": """Write a Python function `max_subarray(nums: list[int]) -> int` that finds the contiguous subarray with the largest sum and returns the sum. The array has at least one element.""",
        "test_code": """
assert max_subarray([-2,1,-3,4,-1,2,1,-5,4]) == 6
assert max_subarray([1]) == 1
assert max_subarray([5,4,-1,7,8]) == 23
assert max_subarray([-1]) == -1
assert max_subarray([-2,-1]) == -1
assert max_subarray([1,2,3,4]) == 10
""",
    },
    {
        "id": "P09",
        "title": "Group Anagrams",
        "category": "Hash Map",
        "difficulty": "Medium",
        "prompt": """Write a Python function `group_anagrams(strs: list[str]) -> list[list[str]]` that groups anagrams together. Return any order of groups, but each group must be sorted alphabetically.""",
        "test_code": """
result = group_anagrams(["eat","tea","tan","ate","nat","bat"])
result = [sorted(g) for g in result]
result.sort()
assert result == [['ate', 'eat', 'tea'], ['bat'], ['nat', 'tan']]

result2 = group_anagrams([""])
assert result2 == [[""]]

result3 = group_anagrams(["a"])
assert result3 == [["a"]]
""",
    },
    {
        "id": "P10",
        "title": "LRU Cache",
        "category": "Design",
        "difficulty": "Medium",
        "prompt": """Implement a Python class `LRUCache` with:
- `__init__(self, capacity: int)` - Initialize with positive capacity.
- `get(self, key: int) -> int` - Return value if key exists, else -1.
- `put(self, key: int, value: int) -> None` - Update or insert. If capacity exceeded, evict the least recently used key.""",
        "test_code": """
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
cache.put(4, 4)
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4
""",
    },
    {
        "id": "P11",
        "title": "Flatten Nested List",
        "category": "Recursion",
        "difficulty": "Medium",
        "prompt": """Write a Python function `flatten(lst) -> list` that flattens a nested list of integers into a single flat list. Input can contain integers and nested lists at any depth.""",
        "test_code": """
assert flatten([1,[2,[3,4],5],6]) == [1,2,3,4,5,6]
assert flatten([]) == []
assert flatten([1,2,3]) == [1,2,3]
assert flatten([[[[1]]]]) == [1]
assert flatten([1,[2],[[3]],[[[4]]]]) == [1,2,3,4]
""",
    },
    {
        "id": "P12",
        "title": "Matrix Rotation",
        "category": "Matrix",
        "difficulty": "Medium",
        "prompt": """Write a Python function `rotate_matrix(matrix: list[list[int]]) -> list[list[int]]` that rotates an NxN matrix 90 degrees clockwise and returns the new matrix.""",
        "test_code": """
assert rotate_matrix([[1,2,3],[4,5,6],[7,8,9]]) == [[7,4,1],[8,5,2],[9,6,3]]
assert rotate_matrix([[1,2],[3,4]]) == [[3,1],[4,2]]
assert rotate_matrix([[1]]) == [[1]]
assert rotate_matrix([[1,2,3,4],[5,6,7,8],[9,10,11,12],[13,14,15,16]]) == [[13,9,5,1],[14,10,6,2],[15,11,7,3],[16,12,8,4]]
""",
    },
    {
        "id": "P13",
        "title": "Word Frequency Counter",
        "category": "String",
        "difficulty": "Easy",
        "prompt": """Write a Python function `word_freq(text: str) -> dict[str, int]` that counts frequency of each word (case-insensitive, split by whitespace). Return a dict of lowercase word to count.""",
        "test_code": """
assert word_freq("the cat sat on the mat") == {"the": 2, "cat": 1, "sat": 1, "on": 1, "mat": 1}
assert word_freq("Hello hello HELLO") == {"hello": 3}
assert word_freq("") == {}
assert word_freq("one") == {"one": 1}
""",
    },
    {
        "id": "P14",
        "title": "Tree Level Order Traversal",
        "category": "Tree",
        "difficulty": "Medium",
        "prompt": """Write Python code with a class `TreeNode` having attributes `val`, `left`, `right`, and a function `level_order(root: TreeNode) -> list[list[int]]` that returns values level by level from left to right. Return empty list if root is None.""",
        "test_code": """
root = TreeNode(3)
root.left = TreeNode(9)
root.right = TreeNode(20)
root.right.left = TreeNode(15)
root.right.right = TreeNode(7)
assert level_order(root) == [[3],[9,20],[15,7]]
assert level_order(None) == []
assert level_order(TreeNode(1)) == [[1]]
""",
    },
    {
        "id": "P15",
        "title": "Longest Palindromic Substring",
        "category": "String",
        "difficulty": "Hard",
        "prompt": """Write a Python function `longest_palindrome(s: str) -> str` that returns the longest palindromic substring. If there are multiple of the same length, return any one.""",
        "test_code": """
assert longest_palindrome("babad") in ("bab", "aba")
assert longest_palindrome("cbbd") == "bb"
assert longest_palindrome("a") == "a"
assert longest_palindrome("ac") in ("a", "c")
r = longest_palindrome("racecar")
assert r == "racecar"
""",
    },
    {
        "id": "P16",
        "title": "Topological Sort",
        "category": "Graph",
        "difficulty": "Hard",
        "prompt": """Write a Python function `topo_sort(num_nodes: int, edges: list[tuple[int,int]]) -> list[int]` that returns a valid topological ordering. edges[i] = (u, v) means u must come before v. If no valid ordering, return empty list.""",
        "test_code": """
result = topo_sort(4, [(0,1),(0,2),(1,3),(2,3)])
assert result.index(0) < result.index(1)
assert result.index(0) < result.index(2)
assert result.index(1) < result.index(3)
assert result.index(2) < result.index(3)
assert topo_sort(2, [(0,1),(1,0)]) == []
assert topo_sort(1, []) == [0]
r = topo_sort(3, [(0,1),(1,2)])
assert r == [0,1,2]
""",
    },
    {
        "id": "P17",
        "title": "Serialize / Deserialize Binary Tree",
        "category": "Tree",
        "difficulty": "Hard",
        "prompt": """Write Python functions `serialize(root) -> str` and `deserialize(data: str)` for a binary tree using `TreeNode` class (val, left, right). deserialize(serialize(tree)) must reconstruct the original tree. Handle None nodes.""",
        "test_code": """
root = TreeNode(1)
root.left = TreeNode(2)
root.right = TreeNode(3)
root.right.left = TreeNode(4)
root.right.right = TreeNode(5)
s = serialize(root)
r = deserialize(s)
assert r.val == 1
assert r.left.val == 2
assert r.right.val == 3
assert r.right.left.val == 4
assert r.right.right.val == 5
assert r.left.left is None
assert deserialize(serialize(None)) is None
""",
    },
    {
        "id": "P18",
        "title": "Median of Two Sorted Arrays",
        "category": "Binary Search",
        "difficulty": "Hard",
        "prompt": """Write a Python function `find_median(nums1: list[int], nums2: list[int]) -> float` that returns the median of two sorted arrays. The overall run time complexity should be O(log(m+n)).""",
        "test_code": """
assert find_median([1,3], [2]) == 2.0
assert find_median([1,2], [3,4]) == 2.5
assert find_median([0,0], [0,0]) == 0.0
assert find_median([], [1]) == 1.0
assert find_median([2], []) == 2.0
assert find_median([1,2,3,4,5], [6,7,8,9,10]) == 5.5
""",
    },
    {
        "id": "P19",
        "title": "Implement Trie",
        "category": "Design",
        "difficulty": "Medium",
        "prompt": """Implement a Python class `Trie` with:
- `__init__(self)` - Initialize.
- `insert(self, word: str) -> None` - Insert a word.
- `search(self, word: str) -> bool` - True if word is in the trie.
- `starts_with(self, prefix: str) -> bool` - True if any word starts with prefix.""",
        "test_code": """
trie = Trie()
trie.insert("apple")
assert trie.search("apple") == True
assert trie.search("app") == False
assert trie.starts_with("app") == True
trie.insert("app")
assert trie.search("app") == True
assert trie.starts_with("b") == False
trie.insert("banana")
assert trie.starts_with("ban") == True
""",
    },
    {
        "id": "P20",
        "title": "Min Stack",
        "category": "Design",
        "difficulty": "Medium",
        "prompt": """Implement a Python class `MinStack` with:
- `__init__(self)` - Initialize.
- `push(self, val: int) -> None` - Push element.
- `pop(self) -> None` - Remove top element.
- `top(self) -> int` - Get top element.
- `get_min(self) -> int` - Retrieve minimum element in O(1).""",
        "test_code": """
s = MinStack()
s.push(-2)
s.push(0)
s.push(-3)
assert s.get_min() == -3
s.pop()
assert s.top() == 0
assert s.get_min() == -2
s.push(1)
assert s.get_min() == -2
""",
    },
]

DIFFICULTY_COUNTS = {"Easy": 0, "Medium": 0, "Hard": 0}
CATEGORY_SET = set()
for p in PROBLEMS:
    DIFFICULTY_COUNTS[p["difficulty"]] += 1
    CATEGORY_SET.add(p["category"])
