import struct
import numpy as np
import tifffile
import zlib

# Function for reading TLV-style (type-length-value) files (needed to read decompressed PIMs)
def read_tlv(data, pos):
    """
    Read one Pascal-style TLV item.

    Returns:
        value, new_pos
    """

    tag = data[pos]
    pos += 1

    # ------------------
    # string
    # ------------------
    if tag == 0x06:

        length = data[pos]
        pos += 1

        value = data[pos:pos+length].decode(
            "latin1",
            errors="replace"
        )

        pos += length

        return {
            "tag": tag,
            "type": "string",
            "value": value
        }, pos

    # ------------------
    # uint8
    # ------------------
    elif tag == 0x02:

        value = struct.unpack_from(
            "B",
            data,
            pos
        )[0]

        pos += 1

        return {
            "tag": tag,
            "type": "uint8",
            "value": value
        }, pos

    # ------------------
    # uint32
    # ------------------
    elif tag == 0x04:

        value = struct.unpack_from(
            "<I",
            data,
            pos
        )[0]

        pos += 4

        return {
            "tag": tag,
            "type": "uint32",
            "value": value
        }, pos

    else:

        return {
            "tag": tag,
            "type": "unknown",
            "value": None
        }, pos

# Main function for converting PIM to TIF. Saves a new .TIF file and returns filename
def convert_pim_to_tif(pim_file, width = 640, height = 480, frame_bytes = 640*480, n_frames = 2):

    with open(pim_file, "rb") as fn:

        # Decompress and read the whole PIM file into memory
        data_all = zlib.decompress(fn.read())

        data_type = 0
        pos = 0

        # Skip over header material until we get to type of 01, indicating start of data
        while data_type != 1:
            data_read, pos = read_tlv(data_all, pos) 
            data_type = data_read["tag"]
        
        # Advance position by 1 o skip start character
        pos += 1

        # Initialize set of frames to hold converted TIF
        frames = []

        # Loop over desired number of frames
        for i in range(n_frames):

            buf = data_all[pos:pos+frame_bytes] # Read one frame into buffer
            pos += frame_bytes                  # Advance pointer by same number

            # Check that we got the right number of bytes
            if len(buf) != frame_bytes:
                raise RuntimeError(
                    f"Frame {i}: expected {frame_bytes} bytes, got {len(buf)}"
                )

            # Convert to unsigned 8-bit int and reshape
            img = np.frombuffer(
                buf,
                dtype="u1"      # unsigned 8-bit int
            ).reshape((height, width))

            # Add to frames
            frames.append(img)

    stack = np.stack(frames)

    # New output file name, just replace .pim with .tif
    outfile = pim_file.replace(".pim", ".tif")

    # Write the TIF file
    tifffile.imwrite(
        outfile,
        stack,
        photometric="minisblack"
    )

    #print(f"Wrote {outfile}")
    return(outfile)
