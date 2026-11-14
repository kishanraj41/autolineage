value = 1000.0
for _ in range(30):
    value = int((value + 0.0004) * 1000) / 1000  # fault
print(value)
