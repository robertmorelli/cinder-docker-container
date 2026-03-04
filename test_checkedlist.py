from __static__ import CheckedList

a = CheckedList[int]([1, 2, 3])
b = CheckedList[int](a)
b.append(4)

print("a:", a)
print("b:", b)
print("Is alias?", a is b)
