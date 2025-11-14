import struct
import numpy as np

class BitStream:
    def __init__(self):
        self.bits = []
        self.current_byte = 0
        self.bit_position = 0
        self.total_bits = 0
    
    def write_bit(self, bit):
        self.current_byte = (self.current_byte << 1) | (bit & 1)
        self.bit_position += 1
        self.total_bits += 1
        
        if self.bit_position == 8:
            self.bits.append(self.current_byte)
            self.current_byte = 0
            self.bit_position = 0
    
    def write_bits(self, value, num_bits):
        for i in range(num_bits - 1, -1, -1):
            self.write_bit((value >> i) & 1)
    
    def get_data(self):
        # Return completed bytes + any remaining bits in current byte
        data = bytes(self.bits)
        if self.bit_position > 0:
            # Pad remaining bits and add final byte
            final_byte = self.current_byte << (8 - self.bit_position)
            data += bytes([final_byte])
        return data, self.total_bits

class CHIMPCompressor:
    def __init__(self):
        self.state = {
            'first': True,
            'pr_value': 0,
            'pr_lead': 0
        }
    
    def count_leading_zeros(self, x):
        """Count leading zeros in a 64-bit integer"""
        if x == 0:
            return 64
        return 63 - (x.bit_length() - 1)
    
    def count_trailing_zeros(self, x):
        """Count trailing zeros in a 64-bit integer"""
        if x == 0:
            return 64
        count = 0
        while (x & 1) == 0:
            count += 1
            x >>= 1
        return count
    
    def float_to_bits(self, value):
        """Convert float to 64-bit integer representation"""
        # Pack float as double (64-bit)
        packed = struct.pack('d', value)
        return struct.unpack('Q', packed)[0]
    
    def compress_float(self, value, stream):
        """Compress a single floating-point value using CHIMP algorithm"""
        # Convert float to 64-bit integer representation
        int_value = self.float_to_bits(value)
        
        if self.state['first']:
            # First value: write full 64 bits
            stream.write_bits(int_value, 64)
            self.state['first'] = False
            self.state['pr_value'] = int_value
            return
        
        # XOR with previous value
        xored_value = int_value ^ self.state['pr_value']
        
        # Count leading and trailing zeros
        lead = self.count_leading_zeros(xored_value)
        trail = self.count_trailing_zeros(xored_value)
        
        if trail > 6:
            stream.write_bit(0)  # Control bit 0
            
            if xored_value == 0:
                stream.write_bit(0)  # All zeros
            else:
                stream.write_bit(1)  # Non-zero
                stream.write_bits(lead, 3)  # Leading zeros count
                
                center_bits = 64 - lead - trail
                stream.write_bits(center_bits, 6)  # Center bits count
                # Write center bits (shift right by trail)
                if center_bits > 0:
                    center_value = xored_value >> trail
                    stream.write_bits(center_value, center_bits)
        else:
            stream.write_bit(1)  # Control bit 1
            
            if lead == self.state['pr_lead']:
                stream.write_bit(0)  # Same leading zeros
                # Write non-leading bits
                if lead < 64:
                    non_lead_bits = 64 - lead
                    non_lead_value = xored_value >> (64 - non_lead_bits)
                    stream.write_bits(non_lead_value, non_lead_bits)
            else:
                stream.write_bit(1)  # Different leading zeros
                stream.write_bits(lead, 3)  # New leading zeros count
                # Write non-leading bits
                if lead < 64:
                    non_lead_bits = 64 - lead
                    non_lead_value = xored_value >> (64 - non_lead_bits)
                    stream.write_bits(non_lead_value, non_lead_bits)
                self.state['pr_lead'] = lead
        
        # Update previous value
        self.state['pr_value'] = int_value
    
    def compress_float_array(self, float_array):
        """Compress an array of floating-point values"""
        stream = BitStream()
        
        for value in float_array:
            self.compress_float(value, stream)
        
        compressed_data, total_bits = stream.get_data()
        return compressed_data, total_bits

# Example usage and testing
def test_chimp_compression():
    test_data=[729.9, 731.3, 731.3, 725.9]

    print("Original data:")
    for i, val in enumerate(test_data):
        print(f"  [{i}]: {val}")
    
    # Compress the data
    compressor = CHIMPCompressor()
    compressed_data, total_bits = compressor.compress_float_array(test_data)
    
    # Calculate statistics
    original_bits = len(test_data) * 64  # 64 bits per double
    compression_ratio =(1 - total_bits / original_bits) * 100
    
    print(f"\nCompression Results:")
    print(f"Original size: {original_bits} bits ({len(test_data)} values × 64 bits)")
    print(f"Compressed size: {total_bits} bits")
    print(f"Compression ratio: {compression_ratio:.2f}%")
    print(f"Compressed data length: {len(compressed_data)} bytes")
    
    # Show bit-level breakdown for first few values
    print(f"\nBit stream analysis:")
    print(f"First value: 64 bits (full value)")
    print(f"Subsequent values: variable bits based on XOR patterns")
    
    return compressed_data, total_bits

# Run the test
if __name__ == "__main__":
    compressed, bits_used = test_chimp_compression()
