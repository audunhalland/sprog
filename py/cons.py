
import debug

import numbers

class Base:
    def __str__(self):
        s = self.__class__.__name__ + '<' + self.sexpr() + '>'
        if hasattr(self, 'tag'):
            s += ' {' + debug.describe_tag(self.tag) + '}'
        return s

class Null(Base):
    def __init__(self):
        pass

    def sexpr(self):
        return '()'

    def fields(self):
        return ()

class Pair(Base):
    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def sexpr(self):
        i = self
        s = '('
        while True:
            s += i.car.sexpr()
            cdr = i.cdr
            if isinstance(cdr, Null):
                break
            elif isinstance(cdr, Pair):
                s += ' '
                i = cdr
            else:
                s += ' . ' + cdr.sexpr()
                break
        return s + ')'

    def fields(self):
        return (self.car, self.cdr)

class Symbol(Base):
    def __init__(self, symbol):
        self.symbol = symbol

    def sexpr(self):
        return self.symbol

    def fields(self):
        return ()

class Void(Base):
    def sexpr(self):
        return '#void'

    def fields(self):
        return ()

class Number(Base):
    def __init__(self, n):
        self.number = n

    def sexpr(self):
        return str(self.number)

    def fields(self):
        return ()

class String(Base):
    def __init__(self, string):
        self.string = string

    def sexpr(self):
        return '"' + self.string + '"'

    def fields(self):
        return ()

class Quote(Base):
    def __init__(self, value):
        self.value = value

    def sexpr(self):
        return "'" + self.value.sexpr()

    def fields(self):
        return [self.value]

def lst(*args):
    p = Null()
    for x in reversed(args):
        p = Pair(from_py(x), p)
    return p

def true():
    return Symbol('true')

def false():
    return Symbol('false')

def is_true(cons):
    return not isinstance(cons, Symbol) or cons.symbol == 'true'

def is_false(cons):
    return isinstance(cons, Symbol) and cons.symbol == 'false'

def debug_str(c):
    d = '#' + c.__class__.__name__
    if hasattr(c, 'tag'):
        d += '[' + debug.describe_tag(c.tag) + ']'
    return d + ' ' + c.sexpr()

def from_py(value):
    if isinstance(value, Base):
        return value
    elif isinstance(value, bool):
        return true() if value else false()
    elif isinstance(value, numbers.Number):
        return Number(value)
    elif isinstance(value, list) or isinstance(value, tuple):
        return lst(*value)
    else:
        raise Exception('unable to interpret value: ', str(value))

def to_py(cons):
    if isinstance(cons, String):
        return cons.string
    elif isinstance(cons, Number):
        return cons.number
    elif isinstance(cons, Symbol):
        return cons.symbol
    else:
        raise Exception('unable to interpret value: ', cons.sexpr())
