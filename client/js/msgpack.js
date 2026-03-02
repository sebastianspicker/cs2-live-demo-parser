// Minimal MessagePack decoder (supports maps, arrays, strings, ints, floats, bool, nil)
// Bounds to prevent DoS from malicious or malformed payloads
const MAX_ELEMENTS = 1024 * 1024;   // max array/map elements
const MAX_BINARY_BYTES = 2 * 1024 * 1024;  // max binary/string length (2MB)

export function msgpack_decode(data) {
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let offset = 0;
    const textDecoder = new TextDecoder();

    function readUint8() {
        if (offset >= bytes.length) throw new RangeError("MessagePack: truncated or malformed input");
        return bytes[offset++];
    }
    function readInt8() { const v = view.getInt8(offset); offset += 1; return v; }
    function readUint16() { const v = view.getUint16(offset); offset += 2; return v; }
    function readInt16() { const v = view.getInt16(offset); offset += 2; return v; }
    function readUint32() { const v = view.getUint32(offset); offset += 4; return v; }
    function readInt32() { const v = view.getInt32(offset); offset += 4; return v; }
    function readFloat32() { const v = view.getFloat32(offset); offset += 4; return v; }
    function readFloat64() { const v = view.getFloat64(offset); offset += 8; return v; }
    function readUint64() {
        const high = readUint32();
        const low = readUint32();
        const value = (BigInt(high) << 32n) + BigInt(low);
        return value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value;
    }
    function readInt64() {
        const high = readInt32();
        const low = readUint32();
        const value = (BigInt(high) << 32n) + BigInt(low);
        return value >= BigInt(Number.MIN_SAFE_INTEGER) && value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value;
    }
    function readBytes(length) {
        if (length < 0 || length > MAX_BINARY_BYTES || offset + length > bytes.length) {
            throw new RangeError("MessagePack: binary/string length out of bounds");
        }
        const slice = bytes.slice(offset, offset + length);
        offset += length;
        return slice;
    }
    function readString(length) {
        const slice = readBytes(length);
        return textDecoder.decode(slice);
    }
    function checkSize(size, label) {
        if (size < 0 || size > MAX_ELEMENTS) {
            throw new RangeError(`MessagePack: ${label} size out of bounds`);
        }
    }

    function decodeValue() {
        const byte = readUint8();
        if (byte <= 0x7f) return byte;
        if (byte >= 0xe0) return byte - 256;
        if ((byte & 0xf0) === 0x80) {
            const size = byte & 0x0f;
            checkSize(size, "fixmap");
            const obj = {};
            for (let i = 0; i < size; i++) {
                const key = decodeValue();
                obj[key] = decodeValue();
            }
            return obj;
        }
        if ((byte & 0xf0) === 0x90) {
            const size = byte & 0x0f;
            checkSize(size, "fixarray");
            const arr = [];
            for (let i = 0; i < size; i++) {
                arr.push(decodeValue());
            }
            return arr;
        }
        if ((byte & 0xe0) === 0xa0) {
            const length = byte & 0x1f;
            checkSize(length, "fixstr");
            return readString(length);
        }
        switch (byte) {
            case 0xc0: return null;
            case 0xc2: return false;
            case 0xc3: return true;
            case 0xc4: {
                const len = readUint8();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: bin8 length out of bounds");
                return readBytes(len);
            }
            case 0xc5: {
                const len = readUint16();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: bin16 length out of bounds");
                return readBytes(len);
            }
            case 0xc6: {
                const len = readUint32();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: bin32 length out of bounds");
                return readBytes(len);
            }
            case 0xca: return readFloat32();
            case 0xcb: return readFloat64();
            case 0xcc: return readUint8();
            case 0xcd: return readUint16();
            case 0xce: return readUint32();
            case 0xcf: return readUint64();
            case 0xd0: return readInt8();
            case 0xd1: return readInt16();
            case 0xd2: return readInt32();
            case 0xd3: return readInt64();
            case 0xd9: {
                const len = readUint8();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: str8 length out of bounds");
                return readString(len);
            }
            case 0xda: {
                const len = readUint16();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: str16 length out of bounds");
                return readString(len);
            }
            case 0xdb: {
                const len = readUint32();
                if (len > MAX_BINARY_BYTES) throw new RangeError("MessagePack: str32 length out of bounds");
                return readString(len);
            }
            case 0xdc: {
                const size = readUint16();
                checkSize(size, "array16");
                const arr = [];
                for (let i = 0; i < size; i++) {
                    arr.push(decodeValue());
                }
                return arr;
            }
            case 0xdd: {
                const size = readUint32();
                checkSize(size, "array32");
                const arr = [];
                for (let i = 0; i < size; i++) {
                    arr.push(decodeValue());
                }
                return arr;
            }
            case 0xde: {
                const size = readUint16();
                checkSize(size, "map16");
                const obj = {};
                for (let i = 0; i < size; i++) {
                    const key = decodeValue();
                    obj[key] = decodeValue();
                }
                return obj;
            }
            case 0xdf: {
                const size = readUint32();
                checkSize(size, "map32");
                const obj = {};
                for (let i = 0; i < size; i++) {
                    const key = decodeValue();
                    obj[key] = decodeValue();
                }
                return obj;
            }
            default:
                // Log warning instead of throwing to prevent client crash
                console.warn(`Unsupported MessagePack byte: 0x${byte.toString(16)} at offset ${offset - 1}`);
                return null;
        }
    }

    return decodeValue();
}
