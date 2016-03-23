
import cons
import cons_util
import debug
import error
import function
import instr
import optimize
import parse

import numbers
import sys

def assert_symbol(sym):
    if not isinstance(sym, cons.Symbol):
        raise error.gen(Error, 'argument is not a symbol', data=sym)

def get_load_literal(i):
    if isinstance(i, instr.Load):
        if isinstance(i.loc, instr.LiteralLocation):
            return i.loc.value
        elif (isinstance(i.loc, instr.UnknownLocation) or
              isinstance(i.loc, instr.EnvSkipLocation) or
              isinstance(i.loc, instr.LocalLocation)):
            return None
        else:
            return i.loc
    return None

def complete_value_defines(iminsref_list, dbg):
    dbg = dbg.value_defines

    # Fix Load/Store definitions
    for iminsref in iminsref_list:
        if not isinstance(iminsref.i, instr.Store) or not iminsref.is_define:
            dbg.d('ignored ', iminsref, ' ', iminsref.i.loc)
            continue

        dbg.d('processing ', iminsref)

        loc = iminsref.i.loc
        if isinstance(iminsref.i.loc, instr.EnvSkipLocation):
            loc = iminsref.i.loc.loc

        if isinstance(loc, IMStampedLocal):
            if not loc.value:
                continue

            is_constant = loc.is_constant()
            value = loc.value
        elif isinstance(loc, PlaceholderLocation):
            is_constant = False
            value = loc.value

        index = iminsref.in_ins.index(iminsref.i)

        dbg.d('complete_value_define! loc=', loc)

        if is_constant:
            # REMOVE Store instruction.
            iminsref.in_ins.erase_ins(index)
            dbg.d('ERASE STORE')
        elif value:
            # ADD Load instruction
            iminsref.in_ins.insert_ins(index, instr.Load(instr.LiteralLocation(value)))
            dbg.d('INSERT LOAD')

class Error(error.Error):
    pass

class PlaceholderLocation(instr.BaseLocation):
    def __init__(self, sym, value):
        self.sym = sym
        self.value = value

    def __str__(self):
        return 'Placeholder(' + self.sym.symbol + ', value=' + str(self.value) + ')'

    def sexpr(self):
        return '#' + str(self)

class IMStampedLocal(instr.BaseLocation):
    def __init__(self, stamp, is_arg, func_block, value, debug_sym):
        """Represents a local definition with yet-to-be-resolved location
        stamp -- definition index
        is_arg -- whether the local is defined as a function argument
        closured -- whether an internal closure refers this local
        func_block -- the block it is defined in
        debug_sym -- for debugging - the name of the variable"""

        self.define_stamp = stamp
        self.target_stamp = -1
        self.last_use_stamp = stamp
        self.is_arg = is_arg
        self.closured = False
        self.overwritten = False
        self.func_block = func_block
        self.value = value
        self.debug_sym = debug_sym

    def is_constant(self):
        return self.value and not self.overwritten

    def __str__(self):
        return 'IMStampedLocal[a=%d, c=%d, d=%d, t=%d, l=%d, o=%d, v=%s, debug_sym=%s]' % \
            (self.is_arg,
             self.closured,
             self.define_stamp,
             self.target_stamp,
             self.last_use_stamp,
             self.overwritten,
             (str(self.value.sexpr()) if self.value else 'None'),
             self.debug_sym.symbol)

class IMInsRef:
    'Representing an opcode of something unknown'
    def __init__(self, i, sym, block, in_ins, is_define):
        """Wraps instruction(s) that is yet to be resolved to a local location
        i - the instruction itself where i.loc is to be updated
        sym - name of the variable
        block - the block from which it is referred"""
        self.i = i
        self.sym = sym
        self.block = block
        self.in_ins = in_ins
        self.is_define = is_define

    def __str__(self):
        return 'IMInsRef[i=' + str(self.i) + ', sym=' + self.sym.symbol + ', d=' + str(self.is_define) + ']'

    def get_stamped(self):
        if isinstance(self.i.loc, instr.EnvSkipLocation):
            return self.i.loc.loc
        else:
            return self.i.loc

    def resolve_constant(self):
        stamped = self.get_stamped()
        if stamped.is_constant():
            self.i.loc = instr.LiteralLocation(stamped.value)
            self.i = None
            return True
        else:
            return False

    def hvtree(self):
        h, v = self.i.hvtree()
        return ([self] + h, v)

# VARIABLE LIFETIME:
# PERMANENT variables: referred from subclosures
# TEMPORARY variables: never referred from subclosures (e.g. as in pure functions)

# It is possible to always keep permanents before temps, and then truncate the Locals
# when only external references are left.
# BUG: If a function captures a continuation, no local optimization should be done.
class StampResolver:
    def __init__(self, func_block, dbg):
        try:
            self.dbg = dbg.stamp_resolver
        except Exception as e:
            print(dir(dbg))
            raise e
        self.func_block = func_block
        self.iminsref_list = []
        self.size = 0

    def get_size(self):
        'Get total size of variable array'
        if len(self.func_block.stamped_locals) == 0:
            return 0
        else:
            return max([s.target_stamp for s in self.func_block.stamped_locals]) + 1

    def setup(self, iminsref_list):
        "Returns iminsref_list than shouldn't be resolved to locals"

        # Step 1: eliminate stamped that are constants
        const_indices = []
        sl = self.func_block.stamped_locals
        for index in range(len(self.func_block.stamped_locals)):
            s = self.func_block.stamped_locals[index]
            if s.is_constant():
                s.define_stamp = -1
                const_indices.append(index)
            else:
                s.define_stamp -= len(const_indices)
                s.last_use_stamp -= len(const_indices)

        self.dbg.d('StampResolver.resolve_nonconstants()', [str(x) for x in sl])
        self.debug(sorted(sl, key=lambda stmp: stmp.define_stamp), 'define_stamp')

        for index in reversed(const_indices):
            self.func_block.stamped_locals[index:index+1] = []

        constant_imins = []
        ignored = []
        for iml in iminsref_list:
            stamped = iml.get_stamped()

            if isinstance(stamped, IMStampedLocal) and stamped.func_block is self.func_block:
                if stamped.is_constant():
                    constant_imins.append(iml)
                else:
                    self.iminsref_list.append(iml)
            else:
                ignored.append(iml)
        self.dbg.d('setup: ignored iminsref=', [str(x) for x in ignored])
        complete_value_defines(constant_imins, self.dbg.parent)

        for iml in constant_imins:
            iml.resolve_constant()

        return ignored

    def debug(self, sl, start_attr):
        if len(sl) == 0:
            return
        end = max([s.last_use_stamp for s in sl]) + 1
        for s in sl:
            start_stamp = getattr(s, start_attr)
            rangestr = ' '*start_stamp
            if s.closured:
                rangestr += '[' + '-'*(end - start_stamp)
            elif start_stamp == s.last_use_stamp:
                rangestr += 'O' + ' '*(end - start_stamp)
            else:
                rangestr += '[' + '-'*(s.last_use_stamp - start_stamp - 1) + ']' + ' '*(end - s.last_use_stamp)
            self.dbg.d(rangestr, ' ', s)

    def move_closured(self, sl):
        "Return number of closured"
        maxlu = max([s.last_use_stamp for s in sl])
        n = 0
        m = {}
        for s in sl:
            if s.closured and not s.is_constant():
                if s.define_stamp in m:
                    s.target_stamp = m[s.define_stamp]
                else:
                    m[s.define_stamp] = n
                    s.target_stamp = n
                    n += 1

        for s in sl:
            if not s.closured:
                s.target_stamp = s.define_stamp + n
                s.last_use_stamp = min(s.last_use_stamp + n, maxlu)

        self.dbg.d('StampResolver: move_closured:')
        self.debug(sorted(sl, key=lambda stmp: stmp.target_stamp), 'target_stamp')
        return n

    def move_nonclosured(self, sl):
        # Find locals that are not arguments and do not overlap
        #nonargs = filter
        pass

    def get_arg_shuffles(self, sl):
        shufs = []
        for s in sl:
            if s.is_arg and s.define_stamp != s.target_stamp:
                shufs.append((s.define_stamp, s.target_stamp))
        if len(shufs) > 0:
            ins = instr.Instructions(debuggable=True)
            shufs = sorted(shufs, key=lambda s: s[0])

            mlr = None
            for shuf in shufs:
                positions = shuf[1] - shuf[0]
                if mlr and positions == mlr.positions and \
                   shuf[0] == mlr.end:
                    # extend range
                    mlr.end += 1
                else:
                    mlr = instr.MoveLocalRange(shuf[0], shuf[0] + 1, positions)
                    ins.append_with_tag(mlr, None)

            self.dbg.d('arg shuffles: ', shufs)
            return ins
        else:
            return None

    def reorder_locals(self):
        # Step 2: Reorder in some way
        if len(self.func_block.stamped_locals) > 1:
            sl = self.func_block.stamped_locals

            self.dbg.d('StampResolver.reorder_locals()')
            self.debug(sorted(sl, key=lambda stmp: stmp.define_stamp), 'define_stamp')

            nclosured = self.move_closured(sl)
            self.move_nonclosured(sl[nclosured:])

            ins = self.get_arg_shuffles(sl)
            self.dbg.d('')
            return ins
        elif len(self.func_block.stamped_locals) == 1:
            self.func_block.stamped_locals[0].target_stamp = 0
            return None
        else:
            return None

    def resolve_locals(self):
        new_locals = {}
        # Fix load/store instructions before removing meta information
        complete_value_defines(self.iminsref_list, self.dbg.parent)
        for iminsref in self.iminsref_list:
            to_resolve = iminsref.i
            if isinstance(to_resolve.loc, instr.EnvSkipLocation):
                to_resolve = to_resolve.loc

            if to_resolve.loc.target_stamp in new_locals:
                to_resolve.loc = new_locals[to_resolve.loc.target_stamp]
            else:
                if to_resolve.loc.target_stamp < 0:
                    raise Error('nonresolved local: ', to_resolve.loc)
                loc = instr.LocalLocation(to_resolve.loc.target_stamp)
                new_locals[to_resolve.loc.target_stamp] = loc
                to_resolve.loc = loc

class Block:
    GLOBAL = 0
    MODULE = 1
    FUNC = 2
    SCOPE = 3

    # Local space optimization
    USE_STAMPS = True

    def __init__(self, block_type, parent, dbg, tag=None, func=None):
        self.block_type = block_type
        self.parent = parent
        self.func = func
        if func:
            func.tag = tag
        self.defines = {}

        self.nesting_level = 0

        # experimental
        self.local_stamp = -1
        self.stamped_locals = []

        self.local_count = 0
        self.local_index = 0
        self.iminsref_list = []
        self.dbg = dbg

    def pop(self, ins=None, env=None):
        def resolve_iminsref_global(iml, env):
            constant = env.lookup_const(iml.sym)
            if constant:
                if isinstance(constant, function.Function):
                    iml.i.loc = constant
                else:
                    iml.i.loc = instr.LiteralLocation(constant)
            else:
                iml.i.loc = instr.UnknownLocation(iml.sym)
                iml.block.mark_func_nonpure()
            return True

        def resolve_all_iminsref_global(l):
            'Resolve all iminsref that can be resolved globally. Return the rest'
            return [x for x in l if not resolve_iminsref_global(x, env)]

        def resolve_iminsref_block(iml):
            c = self.defines.get(iml.sym.symbol, None)
            if isinstance(c, function.Function):
                iml.i.loc = c
                return True
            elif isinstance(c, IMStampedLocal):
                return False
            elif isinstance(c, PlaceholderLocation):
                return False
            elif c:
                # BUG: env skips
                iml.i.loc = instr.LiteralLocation(c)
                return True
            else:
                return False

        def resolve_all_iminsref_in_block(l):
            'Resolve all iminsref defined in this block. Return the rest'
            return [x for x in l if not resolve_iminsref_block(x)]

        'call when done with this block. Returns parent'
        if self.block_type == Block.FUNC:
            assert isinstance(ins, instr.Instructions)

            # Set up function
            if Block.USE_STAMPS:
                sr = StampResolver(self, self.dbg)
                self.iminsref_list = sr.setup(self.iminsref_list)
                move_ins = sr.reorder_locals()
                if isinstance(move_ins, instr.Instructions):
                    ins.prepend_ins(move_ins)
                sr.resolve_locals()
                self.func.size = sr.get_size()
            else:
                self.func.size = self.local_count

            self.func.ins = ins

            complete_value_defines(self.iminsref_list, self.dbg)
            self.parent.iminsref_list.extend(resolve_all_iminsref_in_block(self.iminsref_list))
            self.iminsref_list = []

        elif self.block_type == Block.SCOPE:
            # This scope is reusing the parent scope, whatever it is. Merge into it:
            # Scope (self) locals:         ***| <- self.local_index
            # Parent locals:        *******------| <- self.parent.local_count
            if self.local_index > self.parent.local_count:
                self.parent.local_count = self.local_index
            self.parent.iminsref_list.extend(resolve_all_iminsref_in_block(self.iminsref_list))
            self.iminsref_list = []

        elif self.block_type == Block.MODULE or self.block_type == Block.GLOBAL:
            assert env
            complete_value_defines(self.iminsref_list, self.dbg)
            self.iminsref_list = resolve_all_iminsref_in_block(self.iminsref_list)
            self.iminsref_list = resolve_all_iminsref_global(self.iminsref_list)
            assert len(self.iminsref_list) == 0

        return self.parent

    def check_define_sym(self, sym):
        assert_symbol(sym)
        if sym.symbol in self.defines:
            raise error.gen(Error, 'already defined:', data=sym)
        elif self.nesting_level > 1:
            raise error.gen(Error, 'cannot define outside block:', data=sym)

    def define(self, sym):
        'Context sensitive define'
        if self.block_type == Block.FUNC or self.block_type == Block.SCOPE:
            return self.define_local(sym)
        else:
            return self.define_global(sym)

    def define_value(self, sym, value):
        'Define something as a simple value - potentially a constant definition'
        if self.block_type == Block.FUNC or self.block_type == Block.SCOPE:
            return self.define_local(sym, value=value)
        else:
            return self.define_global(sym, value)

    def define_global(self, sym, value=None):
        self.check_define_sym(sym)

        loc = PlaceholderLocation(sym, value)
        self.defines[sym.symbol] = loc
        return loc

    def define_local(self, sym, is_arg=False, value=None):
        self.check_define_sym(sym)

        func_block = self
        while func_block:
            if func_block.block_type == Block.FUNC:
                break
            func_block = func_block.parent

        if Block.USE_STAMPS:
            func_block.local_stamp += 1
            loc = IMStampedLocal(func_block.local_stamp, is_arg, func_block, value, sym)
            func_block.stamped_locals.append(loc)
        else:
            loc = instr.LocalLocation(func_block.local_index)
            func_block.local_index += 1
            if func_block.local_index > func_block.local_count:
                func_block.local_count = func_block.local_index

        self.defines[sym.symbol] = loc
        return loc

    def define_constant(self, sym, value):
        self.check_define_sym(sym)
        self.defines[sym.symbol] = value
        return value

    def define_arg(self, sym):
        self.func.nargs += 1
        return self.define_local(sym, is_arg=True)

    def define_dotted_arg(self, sym):
        self.func.dotted = True
        return self.define_arg(sym)

    def ref_stamped_local(self, sym, im_stamped, closured):
        b = self
        if closured:
            im_stamped.closured = True
        while b:
            if b.block_type == Block.FUNC:
                im_stamped.last_use_stamp = b.local_stamp
                break
            b = b.parent

    def find_local_location_w_skip(self, sym, closured=False):
        loc = self.defines.get(sym.symbol, None)
        if not loc:
            if not self.parent:
                return (None, None)

            p_loc, p_level = self.parent.find_local_location_w_skip(
                sym, closured or self.block_type==Block.FUNC)

            if p_loc:
                if self.block_type == Block.FUNC:
                    self.func.purity_level = function.PURITY_LEVEL_DEEP_ENV
                elif self.block_type == Block.SCOPE:
                    # Don't add to level
                    return (p_loc, p_level)

                return (p_loc, p_level + 1)
            else:
                return (None, None)
        elif isinstance(loc, instr.LocalLocation):
            return (loc, 0)
        elif isinstance(loc, IMStampedLocal):
            self.ref_stamped_local(sym, loc, closured)
            return (loc, 0)
        else:
            return (None, None)

    def find_global_location(self, sym):
        p = self
        while p:
            loc = self.defines.get(sym.symbol, None)
            if loc:
                return loc
            p = p.parent
        return None

    def get_load_instr(self, sym, ins):
        assert_symbol(sym)
        loc, level = self.find_local_location_w_skip(sym)
        if loc:
            is_stamped = isinstance(loc, IMStampedLocal)

            if level > 0:
                loc = instr.EnvSkipLocation(loc, level)

            i = instr.Load(loc)
        else:
            loc = self.find_global_location(sym)
            if not loc:
                loc = PlaceholderLocation(sym, None)
            i = instr.Load(loc)
            is_stamped = True

        if is_stamped:
            self.iminsref_list.append(IMInsRef(i, sym, self, ins, False))

        return i

    def get_store_instr(self, sym, ins, overwritten):
        assert_symbol(sym)
        loc, level = self.find_local_location_w_skip(sym)
        if loc:
            is_stamped = isinstance(loc, IMStampedLocal)

            if level > 0:
                top_loc = instr.EnvSkipLocation(loc, level)
            else:
                top_loc = loc

            if is_stamped and overwritten:
                loc.overwritten = True

            i = instr.Store(top_loc)
        else:
            loc = self.find_global_location(sym)
            if not loc:
                loc = PlaceholderLocation(sym, None)
            i = instr.Store(loc)
            is_stamped = True

        if is_stamped:
            self.iminsref_list.append(IMInsRef(i, sym, self, ins, not overwritten))

        return i

    def get_unknown_references(self):
        #hack
        return {}

    def mark_func_nonpure(self):
        b = self
        while b:
            if b.block_type == Block.FUNC:
                if b.func.purity_level == function.PURITY_LEVEL_PURE:
                    b.func.purity_level = function.PURITY_LEVEL_SHALLOW_ENV
                return
            b = b.parent

    def __str__(self):
        m = { Block.GLOBAL : 'global',
              Block.MODULE : 'module',
              Block.FUNC : 'func',
              Block.SCOPE : 'scope'}
        chain = []
        b = self
        while b:
            chain.append(b)
            b = b.parent
        return 'Block<' + ','.join([m[x.block_type] for x in chain]) + '>'

class ExclDefineGroup:
    def __init__(self, block):
        self.block = block
        self.original_stamp = block.local_stamp

    def advance(self):
        self.block.local_stamp = self.original_stamp

    def end(self):
        pass

class ExpressionCompiler:
    def __init__(self, env, debuggable=False):
        self.env = env
        self.ins = None
        self.ins_stack = []
        self.block = None
        self.debuggable = debuggable
        self.dbg = env.dbg.comp

    def add(self, i, debug_data=None, tag=None):
        if not self.debuggable:
            self.ins.append(i)
        elif debug_data and hasattr(debug_data, 'tag'):
            self.ins.append_with_tag(i, debug_data.tag)
        elif tag:
            self.ins.append_with_tag(i, tag)
        else:
            self.ins.append_with_tag(i, None)

    def undo(self, undo_index):
        self.ins[undo_index:] = []
        if getattr(self.ins, 'tags'):
            self.ins.tags[undo_index:] = []

    def push_ins(self):
        self.ins_stack.append(self.ins)
        self.ins = instr.Instructions(self.debuggable)

    def pop_ins(self):
        ins = self.ins
        self.ins = self.ins_stack.pop()
        return ins

    def merge_ins(self):
        ins = self.ins
        self.ins = self.ins_stack.pop()
        self.ins.extend(ins)
        if self.debuggable:
            self.ins.tags.extend(ins.tags)

    def function_block(self, func, args, body, tag):
        self.block = Block(Block.FUNC, self.block, self.dbg, tag=tag, func=func)

        while isinstance(args, cons.Pair):
            self.block.define_arg(args.car)
            args = args.cdr

        if isinstance(args, cons.Symbol):
            self.block.define_dotted_arg(args)
        elif not isinstance(args, cons.Null):
            raise error.gen(Error, 'must be a symbol', data=args)

        self.push_ins()

        for expr in cons_util.traverse_list(body):
            self.compile_expr(expr)

        block = self.block
        self.block = self.block.pop(self.pop_ins())
        return block

    def compile_literal(self, literal):
        if not literal:
            raise Exception('no value')
        self.add(instr.Load(instr.LiteralLocation(literal)), debug_data=literal)
        return literal

    def compile_load(self, sym):
        "Load a variable"
        self.add(self.block.get_load_instr(sym, self.ins), debug_data=sym)

    def compile_store(self, head, args):
        "define, set!, etc"
        arglist = [x for x in cons_util.traverse_list(args)]
        if len(arglist) != 2:
            raise error.gen(Error, 'wrong number of arguments to set!', data=head)
        sym = arglist[0]
        assert_symbol(sym)
        self.compile_expr(arglist[1])

        self.add(self.block.get_store_instr(sym, self.ins, True), debug_data=sym)

    def compile_call(self, func, args):
        self.add(instr.PushArgs(), debug_data=func)
        nparams = 0
        for arg in cons_util.traverse_list(args):
            self.compile_expr(arg)
            self.add(instr.Arg(), debug_data=arg)
            nparams += 1
        self.compile_expr(func)
        self.add(instr.Call(nparams), debug_data=func)

    def compile_call_cc(self, head, args):
        # no need for PushArgs
        arglist = [x for x in cons_util.traverse_list(args)]
        if len(arglist) != 1:
            raise error.gen(Error, 'call/cc takes one argument', data=head)
        self.compile_expr(arglist[0])
        self.add(instr.CallCC(), debug_data=head)

    def compile_lambda(self, head, args):
        func = function.Function()
        loc = func
        self.function_block(func, args.car, args.cdr, getattr(head, 'tag', None))
        if func.purity_level == function.PURITY_LEVEL_DEEP_ENV:
            # Add skip location to force environment pickup
            self.dbg.d('deep env for lambda ', str(func), 'level: ', func.purity_level)
            loc = instr.EnvSkipLocation(func, 0)
        self.add(instr.Load(loc), debug_data=head)

    def compile_define(self, head, args):
        if not isinstance(args, cons.Pair):
            raise error.gen(Error, 'no symbol', data=head)

        if isinstance(args.car, cons.Pair):
            # special function syntax
            sym = args.car.car
            tag = getattr(sym, 'tag', None)
            func = function.Function()

            # Define function name in the symbol table - can be referenced directly
            self.block.define_constant(sym, func)

            func_block = self.function_block(func, args.car.cdr, args.cdr, tag)

            if self.block.block_type == Block.GLOBAL:
                # Compiling a global define in a non-module: Need instructions
                self.add(instr.Load(func), debug_data=sym)
                self.add(instr.Store(instr.GlobalFunctionLocation(sym, func_block.get_unknown_references())))
        else:
            if isinstance(args.cdr, cons.Pair):
                constant = self.compile_nonconstant_expr(args.cdr.car)
            else:
                constant = cons.Void()

            if constant:
                self.block.define_value(args.car, constant)
            else:
                self.block.define(args.car)

            self.add(self.block.get_store_instr(args.car, self.ins, False))

    def compile_begin(self, head, args):
        # (begin ...) can contain definitions
        self.block = Block(Block.SCOPE, self.block, self.dbg, tag=getattr(head, 'tag', None))
        for expr in cons_util.traverse_list(args):
            self.compile_expr(expr)
        self.block = self.block.pop()

    def compile_if(self, head, args):
        lst = [x for x in cons_util.traverse_list(args)]
        if len(lst) == 0:
            raise error.gen(Error, 'empty if', data=lst)
        elif len(lst) == 1:
            raise error.gen(Error, 'if: missing true clause', data=lst[0])
        elif len(lst) == 2 or len(lst) == 3:
            constant = self.compile_nonconstant_expr(lst[0])
            if not constant:
                g = ExclDefineGroup(self.block)
                true = self.compile_ins(lst[1])
                g.advance()
                false = self.compile_ins(lst[2] if len(lst) == 3 else cons.Void())
                g.end()
                self.add(instr.If(true, false), debug_data=head)
            elif cons.is_false(constant):
                if len(lst) == 3:
                    self.compile_expr(lst[2])
                else:
                    self.compile_literal(cons.Void())
            else:
                self.compile_expr(lst[1])
        else:
            raise error.gen(Error, 'too many if clauses', data=lst[3])

    def compile_and(self, head, args):
        def comp_rec(p, n):
            if isinstance(p, cons.Null):
                return None
            else:
                constant = self.compile_nonconstant_expr(p.car)
                if constant:
                    self.compile_literal(constant)
                    if cons.is_false(constant):
                        return

                self.push_ins()
                comp_rec(p.cdr, n+1)
                self.add(instr.If(self.pop_ins(), None))

        if isinstance(args, cons.Null):
            self.compile_literal(cons.false())
        else:
            comp_rec(args, 0)

    def compile_or(self, head, args):
        def comp_rec(p, n):
            if isinstance(p, cons.Null):
                return None
            else:
                constant = self.compile_nonconstant_expr(p.car)
                if constant:
                    self.compile_literal(constant)
                    if not cons.is_false(constant):
                        return

                self.push_ins()
                comp_rec(p.cdr, n+1)
                self.add(instr.If(None, self.pop_ins()))

        if isinstance(args, cons.Null):
            self.compile_literal(cons.true())
        else:
            comp_rec(args, 0)

    def compile_list(self, head, args):
        if not isinstance(head, cons.Symbol):
            self.compile_call(head, args)
        elif head.symbol == 'and':
            self.compile_and(head, args)
        elif head.symbol == 'begin':
            self.compile_begin(head, args)
        elif head.symbol == 'call/cc':
            self.compile_call_cc(head, args)
        elif head.symbol == 'define':
            self.compile_define(head, args)
        elif head.symbol == 'if':
            self.compile_if(head, args)
        elif head.symbol == 'lambda':
            self.compile_lambda(head, args)
        elif head.symbol == 'or':
            self.compile_or(head, args)
        elif head.symbol == 'set!':
            self.compile_store(head, args)
        else:
            self.compile_call(head, args)

    def compile_expr(self, e):
        'Generate opcodes for an expression'
        self.block.nesting_level += 1
        if isinstance(e, cons.Pair):
            self.compile_list(e.car, e.cdr)
        elif isinstance(e, cons.Symbol):
            if cons.is_true(e) or cons.is_false(e):
                self.compile_literal(e)
            else:
                self.compile_load(e)
        elif isinstance(e, cons.Quote):
            self.compile_literal(e.value)
        else:
            self.compile_literal(e)
        self.block.nesting_level -= 1

    def compile_nonconstant_expr(self, e, undo_index=None):
        "Generate code only if non-constant expression. Return constant if constant"
        undo_index = undo_index if undo_index else len(self.ins)
        current_index = len(self.ins)
        self.compile_expr(e)
        if len(self.ins) == current_index + 1:
            lit = get_load_literal(self.ins[current_index])
            if lit:
                self.undo(undo_index)
                return lit

        return None

    def compile_add_nonconstant_expr(self, e):
        "Generate code expression code. Return constant if constant, None if nonconstant."
        constant = self.compile_nonconstant_expr(e)
        if constant:
            self.compile_literal(constant)
            return constant
        else:
            return False

    def compile_ins(self, e):
        self.push_ins()
        self.compile_expr(e)
        return self.pop_ins()

    def compile_global(self, e):
        self.block = Block(Block.GLOBAL, self.block, self.dbg)
        ins = self.compile_ins(e)
        self.block = self.block.pop(env=self.env)
        return ins

    def push_module(self):
        self.push_ins()
        self.block = Block(Block.MODULE, self.block, self.dbg)

    def pop_module(self):
        module = self.block
        self.block = module.pop(self.pop_ins(), self.env)
        return module

class CPSTest:
    def __init__(self):
        pass

    def compile_global(self, e):
        pass


def compiler_chain(env, debuggable=True):
    chain = [ExpressionCompiler(env, debuggable=debuggable)]
    #chain.append(optimize.PurityOptimizer(env, verbose=verbose))
    #chain.append(optimize.CallOptimizer(env, verbose=verbose))
    return chain

def run_chain(chain, expr, dbg):
    result = expr
    for c in chain:
        dbg.d('******', c.__class__.__name__, ':')
        result = c.compile_global(result)
        dbg.dump(result)
    return result

def compile_module(i, env, debuggable=True):
    # add all instructions
    dbg = env.dbg.comp
    chain = compiler_chain(env, debuggable=debuggable)
    main = chain[0]
    main.push_module()
    while True:
        try:
            main.compile_expr(parse.parse_iterator(i))
        except parse.NoValueError:
            break
    ins = main.ins
    main.pop_module()
    dbg.d('******[MODULE]*****', main.__class__.__name__, ':')
    dbg.dump(ins)
    return run_chain(chain[1:], ins, dbg)

def compile_expr(expr, env, debuggable=True):
    chain = compiler_chain(env, debuggable=debuggable)
    return run_chain(chain, expr, env.dbg.comp)

def compile_iterator(i, env, debuggable=True):
    chain = compiler_chain(env, debuggable=debuggable)
    while True:
        try:
            yield run_chain(parse.parse_iterator(i), env, env.dbg.comp, debuggable)
        except parse.NoValueError:
            return
