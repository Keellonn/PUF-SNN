"""Independent integer polynomial arithmetic; no galois or production imports.

Translated from the approved backend checkpoint. Coefficients inside polynomial
products are low degree first; external message/codeword vectors are MSB first.
"""


def multiply(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & 64:
            a ^= 0x43
    return result


def construct_generator():
    powers = [1]
    for _ in range(63):
        powers.append(multiply(powers[-1], 2))
    if len(set(powers[:63])) != 63 or powers[-1] != 1:
        raise AssertionError("x must have multiplicative order 63")
    roots, cosets = set(), []
    for exponent in range(1, 11):
        if exponent in roots:
            continue
        current, coset = exponent, []
        while current not in coset:
            coset.append(current)
            current = current * 2 % 63
        roots.update(coset)
        cosets.append(coset)
    coefficients = [1]
    for exponent in sorted(roots):
        product = [0] * (len(coefficients) + 1)
        for index, coefficient in enumerate(coefficients):
            product[index] ^= multiply(coefficient, powers[exponent])
            product[index + 1] ^= coefficient
        coefficients = product
    if set(coefficients) - {0, 1}:
        raise AssertionError("generator is not binary")
    return sum(bit << i for i, bit in enumerate(coefficients)), cosets


def remainder(value, generator):
    while value.bit_length() >= generator.bit_length():
        value ^= generator << (value.bit_length() - generator.bit_length())
    return value


def encode(message):
    generator, _ = construct_generator()
    shifted = message << 27
    return shifted ^ remainder(shifted, generator)


def bits(value, width):
    return tuple(int(bit) for bit in f"{value:0{width}b}")


def flip(response, indices):
    result = list(response)
    for index in indices:
        result[index] ^= 1
    return tuple(result)
