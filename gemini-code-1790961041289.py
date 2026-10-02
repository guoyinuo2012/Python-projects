import math

def calculate_basic(a, op, b):
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        if b == 0:
            return "Error: Division by zero"
        return a / b
    if op == '^' or op == '**':
        return a ** b
    if op == '%':
        return a % b
    if op == 'log_base':
        if a <= 0 or b <= 0 or b == 1:
            return "Error: Invalid log base or argument"
        return math.log(a, b)
    return "Error: Invalid operator"

def calculate_single(op, x):
    try:
        if op == 'sin':
            return math.sin(math.radians(x))
        if op == 'cos':
            return math.cos(math.radians(x))
        if op == 'tan':
            return math.tan(math.radians(x))
        if op == 'asin':
            return math.degrees(math.asin(x))
        if op == 'acos':
            return math.degrees(math.acos(x))
        if op == 'atan':
            return math.degrees(math.atan(x))
        if op == 'sqrt':
            if x < 0:
                return "Error: Square root of negative number"
            return math.sqrt(x)
        if op == 'log' or op == 'log10':
            if x <= 0:
                return "Error: Log undefined for <= 0"
            return math.log10(x)
        if op == 'ln':
            if x <= 0:
                return "Error: Ln undefined for <= 0"
            return math.log(x)
        if op == 'exp':
            return math.exp(x)
        if op == 'fact' or op == '!':
            if x < 0 or not x.is_integer():
                return "Error: Factorial requires non-negative integer"
            return math.factorial(int(x))
        if op == 'abs':
            return abs(x)
    except Exception as e:
        return f"Error: {e}"
    return "Error: Invalid operator"

def parse_val(val_str):
    v = val_str.strip().lower()
    if v == 'pi' or v == 'π':
        return math.pi
    if v == 'e':
        return math.e
    return float(v)

def main():
    print("--- Scientific Calculator ---")
    print("Two-number ops: +, -, *, /, ^ (power), % (mod), log_base")
    print("Single-number ops: sin, cos, tan, asin, acos, atan, sqrt, log (base 10), ln, exp, fact (!), abs")
    print("Constants allowed: pi, e")
    print("Type 'q' at any prompt to quit.")
    
    while True:
        op = input("\nEnter operation or operator: ").strip().lower()
        if op == 'q':
            break

        single_ops = ['sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sqrt', 'log', 'log10', 'ln', 'exp', 'fact', '!', 'abs']
        two_ops = ['+', '-', '*', '/', '^', '**', '%', 'log_base']

        if op in single_ops:
            raw_x = input("Enter number (deg for trig, or 'pi', 'e'): ").strip()
            if raw_x.lower() == 'q':
                break
            try:
                x = parse_val(raw_x)
            except ValueError:
                print("Invalid input.")
                continue
            res = calculate_single(op, x)
            print(f"Result: {res}")

        elif op in two_ops:
            raw_a = input("First number (or 'pi', 'e'): ").strip()
            if raw_a.lower() == 'q':
                break
            raw_b = input("Second number (or 'pi', 'e'): ").strip()
            if raw_b.lower() == 'q':
                break
            try:
                a = parse_val(raw_a)
                b = parse_val(raw_b)
            except ValueError:
                print("Invalid input.")
                continue
            res = calculate_basic(a, op, b)
            print(f"Result: {res}")

        else:
            print("Unknown operation. Try again.")

if __name__ == "__main__":
    main()