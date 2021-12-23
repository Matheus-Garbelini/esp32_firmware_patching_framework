import struct
from .arch_info import Endianness


def u16(h):
    if h < 0:
        return struct.pack("<h", h)
    else:
        return struct.pack("<H", h)


def u32(x):
    if x < 0:
        return struct.pack("<i", x)
    else:
        return struct.pack("<I", x)


def u64(x):
    if x < 0:
        return struct.pack("<q", x)
    else:
        return struct.pack("<Q", x)


def u8(x):
    return struct.pack("<B", x)


class _p2(property):
    def __init__(self, getter, setter, bitsize, signed):
        if bitsize < 1:
            raise TypeError("Cannot create field with less than 1 bit")
        self._bitsize = bitsize
        self._signed = signed
        self._mask = (1 << bitsize) - 1
        super().__init__(getter, setter)

    def __add__(self, other):
        return bit_concat(self, other)


def bit_range(b, e, signed=False):
    """ Create a property which sets a bit range """

    def getter(s):
        return s[b:e]

    def setter(s, v):
        s[b:e] = v

    return _p2(getter, setter, e - b, signed)


def bit(b):
    """ Return a property that sets a single bit """
    return bit_range(b, b + 1)


def bit_concat(*partials):
    """ Group several fields together into a single usable field """

    def getter(s):
        v = 0
        for at in partials:
            v = v << at._bitsize
            v = v | (at.__get__(s) & at._mask)
        return v

    def setter(s, v):
        for at in reversed(partials):
            at.__set__(s, v & at._mask)
            v = v >> at._bitsize

    bitsize = sum(at._bitsize for at in partials)
    signed = partials[0]._signed
    return _p2(getter, setter, bitsize, signed)


class TokenMeta(type):
    def __init__(cls, name, bases, attrs):
        super(TokenMeta, cls).__init__(name, bases, attrs)

        # 'Inherit' info attributes
        if "Info" in attrs:
            for base in bases:
                if hasattr(base, "Info"):
                    for k, v in base.Info.__dict__.items():
                        if k.startswith("__"):
                            continue
                        if not hasattr(cls.Info, k):
                            # print(k, v)
                            setattr(cls.Info, k, v)


# def two_complement(value, bits):
#    mask = 1 << (bits - 1)


class Token(metaclass=TokenMeta):
    """ A token in a stream """

    class Info:
        precode = False  # Set precode to True to indicate a precode
        size = None  # The size in bits of the token type: int
        endianness = Endianness.LITTLE

    ignore_values = ()  # TODO: for optional tokens?

    def __init__(self, initial_bit_value=0):
        assert self.Info.size is not None
        assert self.Info.size % 8 == 0
        self.bit_value = initial_bit_value
        self.mask = (1 << self.Info.size) - 1

    def set_bit(self, i, value):
        """ Sets a specific bit in this token """
        value = bool(value)
        assert i in range(0, self.Info.size)
        mask = 1 << i
        if value:
            self.bit_value |= mask
        else:
            self.bit_value &= ~mask

    def __getitem__(self, key):
        if isinstance(key, slice):
            assert key.step is None
            bits = key.stop - key.start
            assert bits > 0
            limit = 1 << bits
            mask = (limit - 1) << key.start
            value = (self.bit_value & mask) >> key.start
            return value
        else:  # pragma: no cover
            raise KeyError(key)

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.set_bit(key, value)
        elif isinstance(key, slice):
            assert key.step is None
            bits = key.stop - key.start
            assert bits > 0
            limit = 1 << bits
            # TODO: is this an issue?
            # assert value >= 0, value
            if value >= limit:
                raise ValueError(
                    "value {} cannot be fit into {} bits".format(value, bits)
                )
            # TODO: move negative value to field property?
            if value < 0:
                # Assume signed value here, and wrap around
                value = limit + value
                # value = two_complement(value, bits)
            assert (value >= 0) and (value < limit)
            mask = self.mask ^ ((limit - 1) << key.start)
            self.bit_value &= mask
            self.bit_value |= value << key.start
        else:  # pragma: no cover
            raise KeyError(key)

    def encode(self):
        """ Encode the token given some format """
        return self.pack(self.bit_value)

    @classmethod
    def from_data(cls, data):
        """ Instantiate this token type from the given data """
        initial_bit_value = cls.unpack(data)
        return cls(initial_bit_value)

    def fill(self, data):
        self.bit_value = self.unpack(data)

    @classmethod
    def pack(cls, value):
        """ Pack integer value into bytes """
        assert cls.Info.size is not None
        size = cls.Info.size // 8
        if cls.Info.endianness == Endianness.LITTLE:
            byte_numbers = range(size)
        else:
            byte_numbers = reversed(range(size))
        return bytes((value >> (x * 8)) & 0xFF for x in byte_numbers)

    @classmethod
    def unpack(cls, data):
        """ Unpack data into integer value """
        byte_size = cls.Info.size // 8
        if len(data) != byte_size:
            raise TypeError("Incorrect amount of data provided")
        value = 0
        if cls.Info.endianness == Endianness.LITTLE:
            data = reversed(data)
        for byte in data:
            value <<= 8
            value += byte
        return value


class TokenSequence:
    """ A helper to work with a sequence of tokens """

    def __init__(self, tokens):
        self.tokens = tokens

    def __getitem__(self, item):
        return self.tokens.__getitem__(item)

    def set_field(self, field, value):
        """ Set a given field in one of the tokens """
        for token in self.tokens:
            if hasattr(token, field):
                setattr(token, field, value)
                return
        raise KeyError(field)

    def get_field(self, field):
        """ Get the value of a field """
        for token in self.tokens:
            if hasattr(token, field):
                return getattr(token, field)
        raise KeyError(field)

    def encode(self):
        """ Concatenate the token bytes """
        r = bytes()
        for token in self.tokens:
            r += token.encode()
        return r

    def fill(self, data):
        """ Fill the tokens with data """
        offset = 0
        for token in self.tokens:
            size = token.Info.size // 8
            piece = data[offset : offset + size]
            if len(piece) != size:
                raise ValueError("Not enough data for instruction")
            token.fill(data[offset : offset + size])
            offset += size
        if len(data) > offset:
            raise ValueError("Too much data for instruction!")
