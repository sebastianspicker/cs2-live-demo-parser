// Minimal MessagePack decoder (supports maps, arrays, strings, ints, floats, bool, nil)
export function msgpack_decode(data) {
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let offset = 0;
    const textDecoder = new TextDecoder();

    function readUint8() { return bytes[offset++]; }
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
        const slice = bytes.slice(offset, offset + length);
        offset += length;
        return slice;
    }
    function readString(length) {
        const slice = readBytes(length);
        return textDecoder.decode(slice);
    }

    function decodeValue() {
        const byte = readUint8();
        if (byte <= 0x7f) return byte;
        if (byte >= 0xe0) return byte - 256;
        if ((byte & 0xf0) === 0x80) {
            const size = byte & 0x0f;
            const obj = {};
            for (let i = 0; i < size; i++) {
                const key = decodeValue();
                obj[key] = decodeValue();
            }
            return obj;
        }
        if ((byte & 0xf0) === 0x90) {
            const size = byte & 0x0f;
            const arr = [];
            for (let i = 0; i < size; i++) {
                arr.push(decodeValue());
            }
            return arr;
        }
        if ((byte & 0xe0) === 0xa0) {
            const length = byte & 0x1f;
            return readString(length);
        }
        switch (byte) {
            case 0xc0: return null;
            case 0xc2: return false;
            case 0xc3: return true;
            case 0xc4: return readBytes(readUint8());
            case 0xc5: return readBytes(readUint16());
            case 0xc6: return readBytes(readUint32());
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
            case 0xd9: return readString(readUint8());
            case 0xda: return readString(readUint16());
            case 0xdb: return readString(readUint32());
            case 0xdc: {
                const size = readUint16();
                const arr = [];
                for (let i = 0; i < size; i++) {
                    arr.push(decodeValue());
                }
                return arr;
            }
            case 0xdd: {
                const size = readUint32();
                const arr = [];
                for (let i = 0; i < size; i++) {
                    arr.push(decodeValue());
                }
                return arr;
            }
            case 0xde: {
                const size = readUint16();
                const obj = {};
                for (let i = 0; i < size; i++) {
                    const key = decodeValue();
                    obj[key] = decodeValue();
                }
                return obj;
            }
            case 0xdf: {
                const size = readUint32();
                const obj = {};
                for (let i = 0; i < size; i++) {
                    const key = decodeValue();
                    obj[key] = decodeValue();
                }
                return obj;
            }
            default:
                throw new Error(`Unsupported MessagePack byte: 0x${byte.toString(16)}`);
        }
    }

    return decodeValue();
}
