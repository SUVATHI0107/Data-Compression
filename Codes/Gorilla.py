# Replace python_gorilla usage with this pure-Python implementation
import struct

# ---------- bit utilities ----------
class BitWriter:
    def __init__(self):
        self.bits = []  # list of '0'/'1' chars

    def write_bit(self, b):
        self.bits.append('1' if b else '0')

    def write_bits_from_int(self, value: int, nbits: int):
        """Write nbits of 'value' (most-significant first)."""
        if nbits <= 0:
            return
        for i in range(nbits - 1, -1, -1):
            self.bits.append('1' if ((value >> i) & 1) else '0')

    def write_bitstr(self, s: str):
        if s:
            self.bits.extend(list(s))

    def get_bitstring(self) -> str:
        return ''.join(self.bits)


class BitReader:
    def __init__(self, bitstring: str):
        self.bits = bitstring
        self.pos = 0
        self.len = len(bitstring)

    def read_bit(self):
        if self.pos >= self.len:
            raise EOFError("No more bits")
        b = self.bits[self.pos]
        self.pos += 1
        return 1 if b == '1' else 0

    def read_bits_to_int(self, nbits: int) -> int:
        if nbits == 0:
            return 0
        if self.pos + nbits > self.len:
            raise EOFError("Not enough bits")
        v = 0
        end = self.pos + nbits
        for i in range(self.pos, end):
            v = (v << 1) | (1 if self.bits[i] == '1' else 0)
        self.pos = end
        return v

    def read_bitstr(self, nbits: int) -> str:
        if nbits == 0:
            return ''
        if self.pos + nbits > self.len:
            raise EOFError("Not enough bits")
        s = self.bits[self.pos : self.pos + nbits]
        self.pos += nbits
        return s

# ---------- float <-> 64-bit int ----------
def float_to_uint64_bits(f: float) -> int:
    # big-endian to get MSB-first representation (consistent)
    b = struct.pack('>d', f)
    return int.from_bytes(b, byteorder='big', signed=False)


def uint64_bits_to_float(u: int) -> float:
    b = int.to_bytes(u, length=8, byteorder='big', signed=False)
    return struct.unpack('>d', b)[0]

# ---------- leading / trailing zeros ----------
def count_leading_zeros_64(x: int) -> int:
    if x == 0:
        return 64
    return 64 - x.bit_length()


def count_trailing_zeros_64(x: int) -> int:
    if x == 0:
        return 64
    # (x & -x) isolates lowest set bit; bit_length()-1 gives trailing zeros
    return (x & -x).bit_length() - 1

# ---------- Gorilla encode / decode ----------
def encode_gorilla(values):
    """
    values: list[float]
    returns: bitstring (str of '0'/'1')
    """
    writer = BitWriter()
    if not values:
        return writer.get_bitstring()

    # first value: write raw 64 bits
    first = values[0]
    first_bits = float_to_uint64_bits(first)
    writer.write_bits_from_int(first_bits, 64)

    prev_bits = first_bits
    prev_leading = 64
    prev_trailing = 0

    for val in values[1:]:
        curr_bits = float_to_uint64_bits(val)
        xor = prev_bits ^ curr_bits
        if xor == 0:
            # control '0' => identical
            writer.write_bit(0)
        else:
            # first control bit '1'
            writer.write_bit(1)
            leading = count_leading_zeros_64(xor)
            trailing = count_trailing_zeros_64(xor)
            # meaningful bits length
            meaningful_len = 64 - leading - trailing

            # If fits previous window: write '0' (after the first '1')
            if (leading >= prev_leading) and (trailing >= prev_trailing):
                # control bits: '10'
                writer.write_bit(0)
                # write meaningful bits using previous window bounds
                center_bits_len = 64 - prev_leading - prev_trailing
                if center_bits_len > 0:
                    # shift-right by prev_trailing, mask center_bits_len
                    center_value = (xor >> prev_trailing) & ((1 << center_bits_len) - 1)
                    writer.write_bits_from_int(center_value, center_bits_len)
                # prev_leading and prev_trailing unchanged
            else:
                # new window: control bits '11'
                writer.write_bit(1)
                # write leading as 5 bits
                writer.write_bits_from_int(leading, 5)
                # write (meaningful_len - 1) as 6 bits
                writer.write_bits_from_int(meaningful_len - 1, 6)
                # write the meaningful bits
                if meaningful_len > 0:
                    center_value = (xor >> trailing) & ((1 << meaningful_len) - 1)
                    writer.write_bits_from_int(center_value, meaningful_len)
                prev_leading = leading
                prev_trailing = trailing
        prev_bits = curr_bits

    return writer.get_bitstring()


def decode_gorilla(bitstring: str):
    """
    bitstring: str of '0'/'1'
    returns: list[float]
    """
    reader = BitReader(bitstring)
    values = []

    # read first 64 bits raw
    first_int = reader.read_bits_to_int(64)
    values.append(uint64_bits_to_float(first_int))

    prev_bits = first_int
    prev_leading = 64
    prev_trailing = 0

    # read until exhaustion
    while True:
        try:
            b = reader.read_bit()
        except EOFError:
            break
        if b == 0:
            # identical
            curr_bits = prev_bits
            values.append(uint64_bits_to_float(curr_bits))
        else:
            # b == 1 -> read next bit to distinguish '10' or '11'
            second = reader.read_bit()
            if second == 0:
                # '10' -> use previous window bounds
                center_len = 64 - prev_leading - prev_trailing
                if center_len > 0:
                    center_value = reader.read_bits_to_int(center_len)
                    # place center_value at bits [prev_leading .. 63-prev_trailing]
                    xor = (center_value << prev_trailing)
                else:
                    xor = 0
                curr_bits = prev_bits ^ xor
                values.append(uint64_bits_to_float(curr_bits))
            else:
                # '11': new window
                leading = reader.read_bits_to_int(5)
                length_minus1 = reader.read_bits_to_int(6)
                meaningful_len = length_minus1 + 1
                if meaningful_len > 0:
                    center_value = reader.read_bits_to_int(meaningful_len)
                    trailing = 64 - leading - meaningful_len
                    xor = (center_value << trailing)
                else:
                    # edge-case: meaningful_len == 0 (should not usually happen)
                    trailing = 64 - leading
                    xor = 0
                prev_leading = leading
                prev_trailing = trailing
                curr_bits = prev_bits ^ xor
                values.append(uint64_bits_to_float(curr_bits))
        prev_bits = curr_bits

    return values

# ---------- compute_steps: detailed info for UI ----------
def compute_steps(values):
    """
    Similar shape to your old compute_steps: returns a list of dicts describing each step.
    This is useful for your visualizer.
    """
    steps = []
    if not values:
        return steps

    prev_leading = 64
    prev_trailing = 0

    first = values[0]
    prev_bits = float_to_uint64_bits(first)
    stream = ''
    # first step
    stream += format(prev_bits, '064b')
    steps.append({
        "index": 0,
        "current": first,
        "prev_bits": "",
        "current_bits": format(prev_bits, '064b'),
        "xor_bits": "",
        "operation": "first",
        "prev_leading_pre": None,
        "prev_trailing_pre": None,
        "current_leading": None,
        "current_trailing": None,
        "meaningful_bits": "",
        "inserted_bits": format(prev_bits, '064b'),
        "stream_bits": stream,
        "prev_leading_post": prev_leading,
        "prev_trailing_post": prev_trailing,
        "control": None,
    })

    for i, val in enumerate(values[1:], start=1):
        prev_leading_pre = prev_leading
        prev_trailing_pre = prev_trailing
        curr_bits = float_to_uint64_bits(val)
        xor = prev_bits ^ curr_bits
        xor_bin = format(xor, '064b')
        if xor == 0:
            op = "identical (control 0)"
            control = "0"
            leading = None
            trailing = None
            meaningful = ""
            ins = "0"
            stream += ins
        else:
            # first control bit '1'
            leading = count_leading_zeros_64(xor)
            trailing = count_trailing_zeros_64(xor)
            meaningful_len = 64 - leading - trailing
            # check fit previous window
            if (leading >= prev_leading_pre) and (trailing >= prev_trailing_pre):
                op = "fits previous window (control 10)"
                control = "10"
                # meaningful bits from previous window
                center_len = 64 - prev_leading_pre - prev_trailing_pre
                if center_len > 0:
                    center_value = (xor >> prev_trailing_pre) & ((1 << center_len) - 1)
                    meaningful = format(center_value, 'b').rjust(center_len, '0')
                else:
                    meaningful = ""
                ins = '1' + '0' + meaningful
                stream += ins
            else:
                op = "new window (control 11)"
                control = "11"
                meaningful_len = 64 - leading - trailing
                cb = format(leading, '05b')
                mb = format(meaningful_len - 1, '06b')
                if meaningful_len > 0:
                    center_value = (xor >> trailing) & ((1 << meaningful_len) - 1)
                    meaningful = format(center_value, 'b').rjust(meaningful_len, '0')
                else:
                    meaningful = ""
                ins = '1' + '1' + cb + mb + meaningful
                stream += ins
                prev_leading = leading
                prev_trailing = trailing

        steps.append({
            "index": i,
            "current": val,
            "prev_bits": format(prev_bits, '064b'),
            "current_bits": format(curr_bits, '064b'),
            "xor_bits": xor_bin,
            "operation": op,
            "prev_leading_pre": prev_leading_pre,
            "prev_trailing_pre": prev_trailing_pre,
            "current_leading": leading,
            "current_trailing": trailing,
            "meaningful_bits": meaningful,
            "inserted_bits": ins,
            "stream_bits": stream,
            "prev_leading_post": prev_leading,
            "prev_trailing_post": prev_trailing,
            "control": control,
        })
        prev_bits = curr_bits

    return steps

# ---------- quick test ----------
if __name__ == "__main__":
    test = [729.9, 731.3, 731.3, 725.9
]
    bits = encode_gorilla(test)
    decoded = decode_gorilla(bits)
    print("Original:", test)
    print("Decoded :", decoded)
    assert len(test) == len(decoded)
    for a, b in zip(test, decoded):
        # exact bitwise equality expected for floats
        assert a == b
    print("Round-trip OK. Bits length:", len(bits))
     # ---- Added print statements ----
    original_size = len(test) * 64  # 64 bits per float
    compressed_size = len(bits)
    compression_ratio =(1 - compressed_size / original_size) * 100


    print(f"Original size:   {original_size} bits ({original_size / 8:.2f} bytes)")
    print(f"Compressed size: {compressed_size} bits ({compressed_size / 8:.2f} bytes)")
    print(f"Compression ratio: {compression_ratio:.4f}")
