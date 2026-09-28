import struct
import sys

VA_NAMES = {
    0: 'vaNull', 1: 'vaList', 2: 'vaInt8', 3: 'vaInt16', 4: 'vaInt32',
    5: 'vaExtended', 6: 'vaString', 7: 'vaIdent', 8: 'vaFalse', 9: 'vaTrue',
    10: 'vaBinary', 11: 'vaSet', 12: 'vaLString', 13: 'vaNil', 14: 'vaCollection',
    15: 'vaSingle', 16: 'vaCurrency', 17: 'vaDate', 18: 'vaWString', 19: 'vaInt64',
    20: 'vaUTF8String', 21: 'vaUString',
}


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def eof(self):
        return self.pos >= len(self.data)

    def byte(self):
        b = self.data[self.pos]
        self.pos += 1
        return b

    def peek(self):
        return self.data[self.pos]

    def bytes(self, n):
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def int32(self):
        v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def shortstring(self):
        n = self.byte()
        if n == 0:
            return ''
        b = self.bytes(n)
        return b.decode('cp1252', errors='replace')

    def read_value(self):
        tag = self.byte()
        name = VA_NAMES.get(tag, f'UNKNOWN({tag})')
        if tag == 0:  # vaNull
            return None
        elif tag == 1:  # vaList
            items = []
            while True:
                if self.peek() == 0:
                    self.byte()
                    break
                items.append(self.read_value())
            return items
        elif tag == 2:  # vaInt8
            v = self.byte()
            if v > 127:
                v -= 256
            return v
        elif tag == 3:  # vaInt16
            v = struct.unpack_from('<h', self.data, self.pos)[0]
            self.pos += 2
            return v
        elif tag == 4:  # vaInt32
            return self.int32()
        elif tag == 5:  # vaExtended (10-byte float, rare) - skip raw
            b = self.bytes(10)
            return f'<extended:{b.hex()}>'
        elif tag == 6:  # vaString
            return self.shortstring()
        elif tag == 7:  # vaIdent
            return self.shortstring()
        elif tag == 8:  # vaFalse
            return False
        elif tag == 9:  # vaTrue
            return True
        elif tag == 10:  # vaBinary
            n = self.int32()
            b = self.bytes(n)
            return ('BINARY', len(b))
        elif tag == 11:  # vaSet
            items = []
            while True:
                s = self.shortstring()
                if s == '':
                    break
                items.append(s)
            return ('SET', items)
        elif tag == 12:  # vaLString
            n = self.int32()
            b = self.bytes(n)
            return b.decode('cp1252', errors='replace')
        elif tag == 13:  # vaNil
            return None
        elif tag == 14:  # vaCollection
            # Each item is prefixed by a raw flag byte (not a generic value
            # tag): 0 = end of collection; 2 = explicit index byte follows;
            # any other nonzero = plain item marker, no index.
            items = []
            while True:
                flag = self.byte()
                if flag == 0:
                    break
                item_props = {}
                if flag == 2:
                    idx = self.byte()
                    item_props['__index__'] = idx
                while True:
                    pname = self.shortstring()
                    if pname == '':
                        break
                    item_props[pname] = self.read_value()
                items.append(item_props)
            return ('COLLECTION', items)
        elif tag == 15:  # vaSingle
            v = struct.unpack_from('<f', self.data, self.pos)[0]
            self.pos += 4
            return v
        elif tag == 16:  # vaCurrency
            v = struct.unpack_from('<q', self.data, self.pos)[0]
            self.pos += 8
            return v / 10000.0
        elif tag == 17:  # vaDate
            v = struct.unpack_from('<d', self.data, self.pos)[0]
            self.pos += 8
            return v
        elif tag == 18:  # vaWString
            n = self.int32()
            b = self.bytes(n * 2)
            return b.decode('utf-16le', errors='replace')
        elif tag == 19:  # vaInt64
            v = struct.unpack_from('<q', self.data, self.pos)[0]
            self.pos += 8
            return v
        elif tag == 20:  # vaUTF8String
            n = self.int32()
            b = self.bytes(n)
            return b.decode('utf-8', errors='replace')
        elif tag == 21:  # vaUString
            n = self.int32()
            b = self.bytes(n * 2)
            return b.decode('utf-16le', errors='replace')
        else:
            raise ValueError(f'Unknown value tag {tag} at pos {self.pos-1}')

    def read_component(self):
        # Optional prefix flags byte (>= 0xF0): low nibble encodes
        # ffInherited(1)/ffChildPos(2)/ffOwned(4)/ffGlobal(8). If ffChildPos
        # is set, a ChildPos value follows before the class name.
        childpos = None
        if self.peek() >= 0xF0:
            flags = self.byte() & 0x0F
            if flags & 0x02:
                childpos = self.read_value()
        cls = self.shortstring()
        objname = self.shortstring()
        props = []
        while True:
            pname = self.shortstring()
            if pname == '':
                break
            val = self.read_value()
            props.append((pname, val))
        children = []
        while True:
            if self.peek() == 0:
                self.byte()
                break
            children.append(self.read_component())
        return {'class': cls, 'name': objname, 'props': props, 'children': children}


def parse_dfm(data):
    if data[:4] != b'TPF0':
        raise ValueError('not a binary DFM (missing TPF0 signature)')
    r = Reader(data)
    r.pos = 4
    root = r.read_component()
    return root, r


def render(comp, indent=0):
    pad = '  ' * indent
    lines = []
    header = f"{pad}object {comp['name']}: {comp['class']}" if comp['name'] else f"{pad}object {comp['class']}"
    lines.append(header)
    for pname, val in comp['props']:
        if isinstance(val, tuple) and val and val[0] == 'COLLECTION':
            lines.append(f"{pad}  {pname} = <")
            for i, item in enumerate(val[1]):
                lines.append(f"{pad}    item{i} = {{")
                for k, v in item.items():
                    lines.append(f"{pad}      {k} = {format_value(v)}")
                lines.append(f"{pad}    }}")
            lines.append(f"{pad}  >")
        else:
            lines.append(f"{pad}  {pname} = {format_value(val)}")
    for child in comp['children']:
        lines.extend(render(child, indent + 1))
    lines.append(f"{pad}end")
    return lines


def format_value(val):
    if isinstance(val, tuple) and val and val[0] == 'BINARY':
        return f'<binary {val[1]} bytes>'
    if isinstance(val, tuple) and val and val[0] == 'SET':
        return '[' + ', '.join(val[1]) + ']'
    if isinstance(val, tuple) and val and val[0] == 'COLLECTION':
        return f'<collection {len(val[1])} items>'
    if isinstance(val, list):
        return '(' + ' '.join(format_value(v) for v in val) + ')'
    if isinstance(val, str):
        return repr(val)
    return str(val)


if __name__ == '__main__':
    path = sys.argv[1]
    with open(path, 'rb') as f:
        data = f.read()
    root, r = parse_dfm(data)
    text = '\n'.join(render(root))
    print(text)
    remaining = len(data) - r.pos
    if remaining > 0:
        print(f'\n// WARNING: {remaining} trailing bytes not consumed', file=sys.stderr)
