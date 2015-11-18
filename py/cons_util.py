
import cons
import error

def traverse_list(p):
    while True:
        if isinstance(p, cons.Pair):
            yield p.car
            p = p.cdr
        elif isinstance(p, cons.Null):
            return
        else:
            raise error.Error('malformed list', data=p)

def traverse(cons):
    stack = [cons]
    while stack:
        cons = stack.pop()
        yield cons
        fields = [f for f in cons.fields()]
        fields.reverse()
        stack.extend(fields)
