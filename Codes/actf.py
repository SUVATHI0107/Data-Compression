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
        data = bytes(self.bits)
        if self.bit_position > 0:
            final_byte = self.current_byte << (8 - self.bit_position)
            data += bytes([final_byte])
        return data, self.total_bits

class ACTFCompressor:
    def __init__(self):
        self.state = {
            'V2': 0,  # Previous value
            'Xp': 0,  # Previous XOR
            'L_count_p': 0,  # Previous leading count
            'C_count_p': 0   # Previous center count
        }
        self.first_value = True
    
    def float_to_bits(self, value):
        """Convert float to 64-bit integer representation"""
        packed = struct.pack('d', value)
        return struct.unpack('Q', packed)[0]
    
    def bits_to_float(self, bits):
        """Convert 64-bit integer back to float"""
        packed = struct.pack('Q', bits)
        return struct.unpack('d', packed)[0]
    
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
    
    def compress_float(self, V1, stream):
        """Compress a single floating-point value using ACTF algorithm"""
        
        # Convert float to 64-bit integer representation
        V1_bits = self.float_to_bits(V1)
        
        if self.first_value:
            # First value: store full 64 bits and initialize state
            stream.write_bits(V1_bits, 64)
            self.state['V2'] = V1_bits
            self.first_value = False
            return
        
        V2_bits = self.state['V2']
        
        # Check if values are exactly equal
        if V1_bits == V2_bits:
            stream.write_bits(0b00, 2)  # 2 bits: 00
        else:
            Xe = V1_bits ^ V2_bits  # XOR current and previous values
            
            # Calculate counts
            L_count = self.count_leading_zeros(Xe)
            T_count = self.count_trailing_zeros(Xe)
            C_count = 64 - T_count - L_count
            
            if T_count >= 6:
                stream.write_bits(0b01, 2)  # 2 bits: 01
                stream.write_bits(L_count, 3)  # 3 bits for leading count
                
                if L_count >= 12:
                    if C_count == self.state['C_count_p']:
                        stream.write_bits(0b110, 3)  # 3 bits: 110
                        # Write center bits shifted by T_count
                        if C_count > 0:
                            center_bits = Xe >> T_count
                            stream.write_bits(center_bits, C_count)
                    else:
                        if Xe == self.state['Xp']:
                            stream.write_bits(0b111, 3)  # 3 bits: 111
                        else:
                            stream.write_bits(C_count, 6)  # 6 bits for center count
                            # Write center bits shifted by T_count
                            if C_count > 0:
                                center_bits = Xe >> T_count
                                stream.write_bits(center_bits, C_count)
                else:
                    stream.write_bits(C_count, 6)  # 6 bits for center count
                    # Write center bits shifted by T_count
                    if C_count > 0:
                        center_bits = Xe >> T_count
                        stream.write_bits(center_bits, C_count)
            else:
                if L_count == self.state['L_count_p']:
                    stream.write_bits(0b10, 2)  # 2 bits: 10
                    # Write non-leading bits
                    if L_count < 64:
                        non_lead_bits = 64 - L_count
                        non_lead_value = Xe >> (64 - non_lead_bits)
                        stream.write_bits(non_lead_value, non_lead_bits)
                else:
                    stream.write_bits(0b11, 2)  # 2 bits: 11
                    stream.write_bits(L_count, 3)  # 3 bits for leading count
                    # Write non-leading bits
                    if L_count < 64:
                        non_lead_bits = 64 - L_count
                        non_lead_value = Xe >> (64 - non_lead_bits)
                        stream.write_bits(non_lead_value, non_lead_bits)
            
            # Update state for next iteration
            self.state['Xp'] = Xe
            self.state['L_count_p'] = L_count
            self.state['C_count_p'] = C_count
        
        # Update previous value
        self.state['V2'] = V1_bits
    
    def compress_float_array(self, float_array):
        """Compress an array of floating-point values"""
        stream = BitStream()
        
        for value in float_array:
            self.compress_float(value, stream)
        
        compressed_data, total_bits = stream.get_data()
        return compressed_data, total_bits

class ACTFDecompressor:
    def __init__(self):
        self.state = {
            'V2': 0,  # Previous value
            'Xp': 0,  # Previous XOR
            'L_count_p': 0,  # Previous leading count
            'C_count_p': 0   # Previous center count
        }
        self.first_value = True
        self.bit_position = 0
        self.current_byte = 0
        self.data = b''
    
    def bits_to_float(self, bits):
        """Convert 64-bit integer back to float"""
        packed = struct.pack('Q', bits)
        return struct.unpack('d', packed)[0]
    
    def load_data(self, data):
        """Load compressed data for decompression"""
        self.data = data
        self.bit_position = 0
        self.current_byte = 0
        self.byte_index = 0
    
    def read_bit(self):
        """Read a single bit from the compressed data"""
        if self.bit_position == 0:
            if self.byte_index >= len(self.data):
                raise EOFError("No more data to read")
            self.current_byte = self.data[self.byte_index]
            self.byte_index += 1
            self.bit_position = 8
        
        self.bit_position -= 1
        bit = (self.current_byte >> self.bit_position) & 1
        return bit
    
    def read_bits(self, num_bits):
        """Read multiple bits from the compressed data"""
        value = 0
        for _ in range(num_bits):
            value = (value << 1) | self.read_bit()
        return value
    
    def decompress_float(self):
        """Decompress a single floating-point value"""
        if self.first_value:
            # First value: read full 64 bits
            V1_bits = self.read_bits(64)
            self.state['V2'] = V1_bits
            self.first_value = False
            return self.bits_to_float(V1_bits)
        
        # Read the first 2 bits to determine the case
        flag = self.read_bits(2)
        
        if flag == 0b00:  # Values are equal
            V1_bits = self.state['V2']
        else:
            if flag == 0b01:  # T_count >= 6 case
                L_count = self.read_bits(3)
                
                # Check if we have L_count >= 12 subcases
                if L_count >= 12:
                    subflag = self.read_bits(3)
                    
                    if subflag == 0b110:  # C_count equals previous
                        C_count = self.state['C_count_p']
                        center_bits = self.read_bits(C_count) if C_count > 0 else 0
                        # Reconstruct XOR value
                        Xe = center_bits << (64 - L_count - C_count)
                    
                    elif subflag == 0b111:  # Xe equals previous XOR
                        Xe = self.state['Xp']
                        C_count = 64 - L_count - self.count_trailing_zeros(Xe)
                    
                    else:  # Regular case with C_count written
                        C_count = subflag << 3 | self.read_bits(3)  # 6 bits total
                        center_bits = self.read_bits(C_count) if C_count > 0 else 0
                        # Reconstruct XOR value
                        Xe = center_bits << (64 - L_count - C_count)
                
                else:  # Regular T_count >= 6 case
                    C_count = self.read_bits(6)
                    center_bits = self.read_bits(C_count) if C_count > 0 else 0
                    # Reconstruct XOR value
                    Xe = center_bits << (64 - L_count - C_count)
            
            else:  # flag == 0b10 or 0b11
                if flag == 0b10:  # Same leading zeros
                    L_count = self.state['L_count_p']
                    non_lead_bits = 64 - L_count
                    non_lead_value = self.read_bits(non_lead_bits) if non_lead_bits > 0 else 0
                    # Reconstruct XOR value
                    Xe = non_lead_value << (64 - non_lead_bits)
                
                else:  # flag == 0b11, different leading zeros
                    L_count = self.read_bits(3)
                    non_lead_bits = 64 - L_count
                    non_lead_value = self.read_bits(non_lead_bits) if non_lead_bits > 0 else 0
                    # Reconstruct XOR value
                    Xe = non_lead_value << (64 - non_lead_bits)
                
                # Update state
                self.state['L_count_p'] = L_count
                C_count = 64 - L_count - self.count_trailing_zeros(Xe)
                self.state['C_count_p'] = C_count
            
            # Reconstruct current value from XOR and previous value
            V1_bits = self.state['V2'] ^ Xe
            self.state['Xp'] = Xe
        
        # Update previous value
        self.state['V2'] = V1_bits
        return self.bits_to_float(V1_bits)
    
    def count_trailing_zeros(self, x):
        """Count trailing zeros in a 64-bit integer"""
        if x == 0:
            return 64
        count = 0
        while (x & 1) == 0:
            count += 1
            x >>= 1
        return count
    
    def decompress_float_array(self, compressed_data, num_values):
        """Decompress an array of floating-point values"""
        self.load_data(compressed_data)
        decompressed_data = []
        
        for _ in range(num_values):
            value = self.decompress_float()
            decompressed_data.append(value)
        
        return decompressed_data

# Example usage and testing
def test_actf_compression():
    test_data=[729.9, 731.3, 731.3, 725.9]
    print(f"Total points: {len(test_data)}")
    print("Original data:")
    for i, val in enumerate(test_data):
        print(f"  [{i:2d}]: {val:.10f}")
    
    # Compress the data
    compressor = ACTFCompressor()
    compressed_data, total_bits = compressor.compress_float_array(test_data)
    
    # Calculate statistics
    original_bits = len(test_data) * 64
    compression_ratio = (1 - total_bits / original_bits) * 100
    
    print(f"\nCompression Results:")
    print(f"Original size: {original_bits} bits ({len(test_data)} values × 64 bits)")
    print(f"Compressed size: {total_bits} bits")
    print(f"Compression ratio: {compression_ratio:.2f}%")
    print(f"Compressed data length: {len(compressed_data)} bytes")
    
    # Decompress to verify
    decompressor = ACTFDecompressor()
    


# Run the test
if __name__ == "__main__":
    compressed = test_actf_compression()
