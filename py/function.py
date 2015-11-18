
import cons
import cons_util
import debug
import instr

class Base(cons.Base):
    def debug_post(self, env, args):
        print(self.sexpr(), [x.sexpr() for x in args], ' => ', env.exe.value.sexpr())

    def sexpr(self):
        return '#function.' + type(self).__name__

class Locals:
    'local environment for Function'
    def __init__(self, size, parent):
        self.mem = [None]*size
        self.parent = parent

    def depth(self):
        l = self
        d = 0
        while l:
            d += 1
            l = l.parent
        return d

    def skip(self, n):
        l = self
        while l:
            if n == 0:
                return l
            else:
                l = l.parent
                n -= 1
        return None

    def apply_args(self, args):
        for i, arg in enumerate(args):
            self.mem[i] = arg

    def move_range(self, start, end, positions):
        #debug.d('pre move range: ', self.mem)
        items = self.mem[start:end]
        self.mem[start:end] = []
        self.mem[start+positions:start+positions] = items
        #debug.d('post move range: ', self.mem)

    def lookup(self, index, level):
        if level == 0:
            return self.mem[index]
        else:
            return self.parent.lookup(index, level-1)

    def assign(self, index, level, value):
        if level == 0:
            self.mem[index] = value
        else:
            self.parent.assign(index, level-1, value)

    def __repr__(self):
        return 'local: [' + ','.join([str(x) for x in self.mem]) + ']'

# Purity levels
PURITY_LEVEL_DEEP_ENV = 0 # lowest level
PURITY_LEVEL_SHALLOW_ENV = 1 # env level == 1
PURITY_LEVEL_PURE = 2

class Function(Base, instr.BaseLocation):
    'First class function - implemented with instr - no closure'

    def __init__(self):
        self.ins = None
        self.nargs = 0
        self.size = 0
        self.dotted = False
        self.purity_level = PURITY_LEVEL_PURE
        self.tag = None

    def __str__(self):
        label = 'Function(%d|%d' % (self.nargs, self.size)

        if self.purity_level == PURITY_LEVEL_DEEP_ENV:
            label += ' d>1'
        elif self.purity_level == PURITY_LEVEL_SHALLOW_ENV:
            label += ' d=1'
        elif self.purity_level == PURITY_LEVEL_PURE:
            label += ' PURE'
        else:
            raise error.Error('unknown purity value')

        label += ' ' + debug.describe_tag(self.tag)
        label += ')'
        return label

    def is_pure(self):
        return self.purity_level == PURITY_LEVEL_PURE

    def hvtree(self):
        return ([self, self.ins], self.ins)

    def get_ins(self):
        return [self.ins]

    def sexpr(self):
        return '#' + str(self)

    def call(self, env, args, inh_local=None):
        n = self.nargs
        if self.dotted:
            args = args[:n-1] + [cons.from_py(args[n-1:])]
        else:
            env.assert_arglen(args, n)

        # Assign local memory to the function
        l = Locals(self.size, inh_local)
        l.apply_args(args)
        # TODO: A function containing no lambdas can just extend
        # the current local? BUT What about continuations then?
        env.exe.push_local_autopop(l)

        env.exe.push_ins(self.ins)

class Closure(Base):
    'Instantiated first class function, with inherited environment'

    def __init__(self, function, inh_local):
        self.function = function
        self.inh_local = inh_local

    def call(self, env, args):
        self.function.call(env, args, self.inh_local)

class Apply(Base):
    def call(self, env, args):
        env.assert_arglen(args, 2)
        env.exe.value = args[0]
        pyargs = [x for x in cons_util.traverse_list(args[1])]
        env.exe.apply_function(env, args=pyargs)

class Generic(Base):
    def __init__(self, name, func, pure):
        self.name = name
        self.func = func
        self.pure = pure

    def call(self, env, args):
        try:
            env.exe.value = self.func(*args)
        except TypeError as e:
            env.exe.error(str(type(e)) + ' ' + str(e))
            env.exe.value = error.Error(str(e))
        except Exception as e:
            env.exe.error(str(e))
            env.exe.value = error.Error(str(e))

    def is_pure(self):
        return self.pure

    def sexpr(self):
        return '#' + self.name

class PyOp(Base):
    def __init__(self, py_func):
        self.py_func = py_func

    def call(self, env, args):
        py_args = [cons.to_py(x) for x in args]
        if len(args) == 0:
            env.exe.error('no arguments')
        else:
            result = py_args[0]
            for arg in py_args[1:]:
                result = self.py_func(result, arg)
            #print('called py_function: ' + str(self.py_func) + ','.join([str(x) for x in py_args]) + ' result: ' + str(result))
            env.exe.value = cons.from_py(result)

    def is_pure(self):
        return True

    def sexpr(self):
        return '#function.PyOp' + str(self.py_func)
