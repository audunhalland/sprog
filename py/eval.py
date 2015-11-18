
import cons
import debug
import error
import function
import instr

import copy

class ExecEnv:
    # cached
    pop_local = instr.Instructions()
    pop_local.append(instr.PopLocals())

    def __init__(self, ins):
        # Result register
        self.value = None

        # Programs and program counter
        self.ins = ins
        self.pc = 0
        self.ins_pc_stack = []

        # Function environments
        self.local = None
        self.local_stack = []

        # Function calling
        self.args = []
        self.args_stack = []

    def __next__(self):
        while self.pc == len(self.ins):
            if len(self.ins_pc_stack) == 0:
                raise StopIteration
            else:
                (self.ins, self.pc) = self.ins_pc_stack.pop()

        i = self.ins[self.pc]
        self.pc += 1
        return i

    def push_ins(self, ins):
        if ins:
            if self.pc < len(self.ins):
                #debug.d('push ins, pc=', self.pc)
                self.ins_pc_stack.append((self.ins, self.pc))
            self.ins = ins
            self.pc = 0

    def push_local_autopop(self, local):
        self.local_stack.append(self.local)
        self.local = local
        self.push_ins(self.pop_local)

    def pop_args(self):
        args = self.args
        self.args = self.args_stack.pop()
        return args

    def apply_function(self, env, args=None):
        try:
            self.value.call(env, args if args else self.pop_args())
        except AttributeError:
            self.error('not a function', data=self.value)

    def debug_last_ins(self, dbg):
        index = self.pc - 1
        items = ['ins: ', self.ins[index]]
        tag = self.ins.tags[index] if hasattr(self.ins, 'tags') else None
        if tag:
            items.append(' ' + debug.describe_tag(tag))
        dbg.d(*items)

    def error(self, msg, **kw):
        if hasattr(self.ins, 'tags'):
            tag = self.ins.tags[self.pc - 1]
            e = error.Error(msg, tag=tag, **kw)
        else:
            e = error.Error(msg, **kw)

        self.value = e
        raise e

    def call(self, env, args):
        "Call as continuation object"
        if len(args) != 1:
            env.exe.error('ExecEnv takes one argument')
        self.value = args[0]
        env.exe = self

    def sexpr(self):
        return '#exec_env'

class Env:
    def __init__(self, dbg):
        self.exe = None

        self.glob_const = {}
        self.glob = {}
        self.func_unknowns = {}
        self.dbg = dbg

    def lookup_unknown(self, sym):
        try:
            return self.glob_const[sym.symbol]
        except KeyError:
            try:
                return self.glob[sym.symbol]
            except KeyError:
                self.exe.error('unknown variable', data=sym)

    def set_unknown(self, sym):
        if sym.symbol in self.glob_const:
            self.exe.error('cannot set constant', data=sym)
        self.glob[sym.symbol] = self.exe.value

    def resolve_function_unknowns(self, caller, callee, symbol):
        self.dbg.eval.d('resolve_function_unknowns(', caller, ', ', callee, ', ', symbol, ')')
        return False

    def resolve_unknowns(self, func, symbol, unknown_references):
        self.dbg.eval.d('resolve_unknowns, new function ', symbol, ' unknown: ', unknown_references)
        if symbol in self.func_unknowns:
            # Resolve all functions referring to the new one
            for func2 in self.func_unknowns[symbol]:
                if self.resolve_function_unknowns(func2, func, symbol):
                    pass

        for unk in unknown_references:
            d = self.func_unknowns.get(unk, None)
            if d:
                d[func] = None
            else:
                self.func_unknowns[unk] = {func:None}

    def define_global_function(self, sym, unknown_references):
        if sym.symbol in self.glob_const:
            self.exe.error('cannot redefine constant', data=sym)
        self.glob_const[sym.symbol] = self.exe.value
        self.resolve_unknowns(self.exe.value, sym.symbol, unknown_references)

    def lookup_const(self, sym):
        return self.glob_const.get(sym.symbol, None)

    def assert_arglen(self, args, n):
        if len(args) != n:
            self.exe.error('wrong number of arguments, should be ' + str(n))

    def eval_noexcept(self, ins, **kw):
        self.exe = ExecEnv(ins)
        try:
            self.loop(**kw)
        except StopIteration:
            ret = self.exe.value
            self.exe = None
            return ret

    def eval(self, ins, **kw):
        try:
            return self.eval_noexcept(ins, **kw)
        except error.Error as e:
            print(e)
            return self.exe.value

    def loop(self):
        dbg = self.dbg.eval

        while True:
            i = self.exe.__next__()

            if dbg.enabled:
                self.exe.debug_last_ins(dbg)

            if isinstance(i, instr.Call):
                self.exe.apply_function(self)
            elif isinstance(i, instr.CallCC):
                self.exe.apply_function(self, [copy.copy(self.exe)])
            elif isinstance(i, instr.If):
                self.exe.push_ins(i.true if cons.is_true(self.exe.value) else i.false)
            elif isinstance(i, instr.Load):
                loc = i.loc

                if isinstance(loc, instr.LiteralLocation):
                    self.exe.value = loc.value
                elif isinstance(loc, instr.LocalLocation):
                    self.exe.value = self.exe.local.lookup(loc.index, 0)
                elif isinstance(loc, instr.EnvSkipLocation):
                    next = loc.loc
                    if isinstance(next, instr.LocalLocation):
                        # Load from this or parent environment
                        self.exe.value = self.exe.local.lookup(next.index, loc.skip)
                    elif isinstance(next, function.Function):
                        # Function with inherited environment
                        # debug.d('load skip func!!!', loc)
                        self.exe.value = function.Closure(next, self.exe.local.skip(loc.skip))
                    else:
                        self.exe.error('cannot skip', data=target)
                elif isinstance(loc, instr.UnknownLocation):
                    self.exe.value = self.lookup_unknown(loc.sym)
                elif isinstance(loc, function.Function):
                    # Function with no inherited environment
                    self.exe.value = loc
                else:
                    self.exe.error('unknown location for Load:', data=loc)
            elif isinstance(i, instr.MoveLocalRange):
                self.exe.local.move_range(i.start, i.end, i.positions)
            elif isinstance(i, instr.PopLocals):
                self.exe.local = self.exe.local_stack.pop()
            elif isinstance(i, instr.PushArgs):
                self.exe.args_stack.append(self.exe.args)
                self.exe.args = []
            elif isinstance(i, instr.Store):
                loc = i.loc

                if isinstance(loc, instr.LocalLocation):
                    self.exe.local.assign(loc.index, 0, self.exe.value)
                elif isinstance(loc, instr.EnvSkipLocation):
                    self.exe.local.assign(loc.loc.index, loc.skip, self.exe.value)
                elif isinstance(loc, instr.UnknownLocation):
                    self.set_unknown(loc.sym)
                elif isinstance(loc, instr.GlobalFunctionLocation):
                    self.define_global_function(loc.sym, loc.unknown_references)
                else:
                    self.exe.error('cannot Store to location: ', data=loc)
            elif isinstance(i, instr.Arg):
                self.exe.args.append(self.exe.value)
            elif isinstance(i, instr.ArgPrepend):
                self.exe.args = [self.exe.value] + self.exe.args
            else:
                self.exe.error('cannot execute instruction: ', i)

            dbg.d('=> ', str(self.exe.value))
