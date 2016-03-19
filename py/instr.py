
import cons
import debug

#
# Locations for Load/Store
#

class BaseLocation:
    def get_ins(self):
        return []

    def hvtree(self):
        return ([self], [])

class LiteralLocation(BaseLocation):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return 'Literal(' + self.value.sexpr() + ')'

    def hvtree(self):
        if getattr(self.value, 'tree', None):
            h, v = self.value.hvtree()
            return ([self] + h, v)
        else:
            return ([self], [])

class LocalLocation(BaseLocation):
    def __init__(self, index):
        self.index = index

    def __str__(self):
        return 'Local(' + str(self.index) + ')'

class EnvSkipLocation(BaseLocation):
    def __init__(self, loc, skip):
        self.loc = loc
        self.skip = skip

    def __str__(self):
        return 'Skip(' + str(self.skip) + ')'

    def hvtree(self):
        h, v = self.loc.hvtree()
        return ([self] + h, v)

class UnknownLocation(BaseLocation):
    def __init__(self, sym):
        self.sym = sym

    def __str__(self):
        return 'Unknown(' + self.sym.sexpr() + ')'

class GlobalFunctionLocation(BaseLocation):
    def __init__(self, sym, unknown_references):
        self.sym = sym
        self.unknown_references = unknown_references

    def __str__(self):
        return 'GlobalFunction(' + self.sym.sexpr() + ')'

#
# High level instruction definition
#

class BaseInstr:
    def dump(self, guard, level):
        idump(self, guard, level)

    def hvtree(self):
        return ([self], [])

    def get_ins(self):
        return []

    def __str__(self):
        return self.__class__.__name__

class Arg(BaseInstr):
    'Append arg'

class ArgPrepend(BaseInstr):
    'Prepend arg'

class Call(BaseInstr):
    def __init__(self, nparams):
        # Ignored for now. Arg instruction is the current argument counter
        pass

class CallCC(BaseInstr):
    pass

class If(BaseInstr):
    def __init__(self, true, false):
        self.true = true
        self.false = false

    def hvtree(self):
        return ([self], [self.true, self.false])

    def get_ins(self):
        return [self.true, self.false]

class Load(BaseInstr):
    def __init__(self, loc):
        self.loc = loc

    def hvtree(self):
        h, v = self.loc.hvtree()
        return ([self] + h, v)

    def get_ins(self):
        return self.loc.get_ins()

class MoveLocalRange(BaseInstr):
    def __init__(self, start, end, positions):
        self.start = start
        self.end = end
        self.positions = positions

    def __str__(self):
        return 'MoveLocalRange([%d:%d] %s%d)' % (self.start, self.end, '+' if self.positions > 0 else '', self.positions)

class PopLocals(BaseInstr):
    pass

class PushArgs(BaseInstr):
    pass

class Store(BaseInstr):
    def __init__(self, loc):
        self.loc = loc

    def hvtree(self):
        h, v = self.loc.hvtree()
        return ([self] + h, v)

    def get_ins(self):
        return self.loc.get_ins()

class Instructions(list):
    def __init__(self, debuggable=False, data=None):
        if debuggable:
            self.tags = []
        if data:
            self.extend(data)

    def prepend_ins(self, other):
        self[0:0] = other
        if hasattr(self, 'tags'):
            self.tags[0:0] = other.tags

    def erase_ins(self, index):
        self[index:index+1] = []
        if hasattr(self, 'tags'):
            self.tags[index:index+1] = []

    def insert_ins(self, index, i):
        self[index:index] = [i]
        if hasattr(self, 'tags'):
            self.tags[index:index] = [None]

    def append_with_tag(self, i, tag):
        self.append(i)
        self.tags.append(tag)

    def hvtree(self):
        return ([self], self)

    def __str__(self):
        return 'instr(' + str(len(self)) + ')'
