
import cons as c
import debug
import error

import sys

TERM_EOF = 0
TERM_CLOSE_PAREN = 1
TERM_WHITESPACE = 2
TERM_DQUOTE = 3
TERM_DOT = 4
TERM_MATCHED = 5

list_id = 0

class NoValueError(error.Error):
    pass

class EOFError(error.Error):
    pass

class SingleLineError(error.Error):
    pass

def parse_iterator(iterator):
    can_tag = hasattr(iterator, 'get_tag')

    def get_tag():
        return iterator.get_tag() if can_tag else None

    def attach_tag(cons, tag):
        if tag:
            cons.tag = tag
        return cons

    def create_symbolish(s, tag):
        try:
            val = c.Number(int(s))
        except:
            try:
                val = c.Number(float(s))
            except:
                val = c.Symbol(s)
        return attach_tag(val, tag)

    def parse_symbolish(i, init):
        tag = get_tag()
        string = init
        while True:
            try:
                ch = i.__next__()
                if ch == ' ' or ch == '\n':
                    return (create_symbolish(string, tag), TERM_WHITESPACE)
                elif ch == ')':
                    return (create_symbolish(string, tag), TERM_CLOSE_PAREN)
                else:
                    string += ch
            except StopIteration:
                return (create_symbolish(string, tag), TERM_EOF)

    def parse_list(i):
        # debug
        global list_id
        lid = list_id
        list_id += 1

        tag = get_tag()
        (element, term) = parse_unknown(i)
        #debug.d('parse list ', lid, ' (initial): ', element, ' ', 'term=', term)
        if not element:
            if term != TERM_CLOSE_PAREN:
                raise error.Error('weird list', tag=tag)
            return (attach_tag(c.Null(), tag), TERM_MATCHED)
        else:
            head = None
            current = None
            index = 0
            while True:
                #debug.d('parse list ', lid, '#', index, ': ', element, ' term=', term)
                if term == TERM_CLOSE_PAREN:
                    if not element:
                        current.cdr = attach_tag(c.Null(), tag)
                    elif current:
                        current.cdr = attach_tag(c.Pair(element, attach_tag(c.Null(), get_tag())), tag)
                    else:
                        head = attach_tag(c.Pair(element, attach_tag(c.Null(), get_tag())), tag)
                    break
                elif term == TERM_DOT:
                    tag = get_tag()
                    (element, term) = parse_unknown(i)
                    #debug.d('parse list ', lid, ' (post-dot)', index, ': ', element, ' term=', term)
                    if term != TERM_CLOSE_PAREN:
                        (_, term) = parse_close_paren(i)
                    if term != TERM_CLOSE_PAREN:
                        raise error.Error('malformed dot notation', tag=get_tag())
                    current.cdr = element
                    break
                elif term == TERM_EOF:
                    raise error.gen(EOFError, 'non-terminated list', tag=get_tag())
                else:
                    p = attach_tag(c.Pair(element, None), tag)
                    if current:
                        current.cdr = p
                    else:
                        head = p
                    current = p

                tag = get_tag()
                (element, term) = parse_unknown(i)
                index += 1
            return (head, TERM_MATCHED)

    def parse_singleline_comment(i):
        if not can_tag:
            raise error.gen(SingleLineError, msg="single line comment not supported")
        tag = get_tag()
        row = tag[0].row
        try:
            while True:
                i.__next__()
                if get_tag()[0].row != row:
                    return (None, TERM_MATCHED)
        except StopIteration:
            raise NoValueError()

    def parse_multiline_comment(i):
        try:
            while True:
                ch = i.__next__()
                if ch == '|':
                    ch = i.__next__()
                    if ch == '#':
                        return (None, TERM_MATCHED)
        except StopIteration:
            raise error.gen(EOFError, 'non-terminated comment', tag=get_tag())

    def parse_string(i):
        tag = get_tag()
        string = ''
        try:
            while True:
                ch = i.__next__()
                if ch == '\\':
                    # Escape sequences
                    ch = i.__next__()
                    if ch == 'n':
                        string += '\n'
                    elif ch == '\\':
                        string += '\\'
                    else:
                        raise error.Error('invalid escape character: \\' + ch)
                elif ch == '"':
                    return (attach_tag(c.String(string), tag), TERM_DQUOTE)
                else:
                    string += ch
        except StopIteration:
            raise error.gen(EOFError, 'non-terminated string', tag=get_tag())

    def parse_close_paren(i):
        while True:
            ch = i.__next__()
            if ch.isspace():
                continue
            if ch == ')':
                return (None, TERM_CLOSE_PAREN)
            else:
                return (None, TERM_UNEXPECTED)

    def parse_unknown(i):
        while True:
            try:
                ch = i.__next__()
            except StopIteration:
                return (None, TERM_EOF)

            if ch.isspace():
                continue
            elif ch == ')':
                return (None, TERM_CLOSE_PAREN)
            elif ch == '.':
                return (None, TERM_DOT)
            elif ch == '(':
                return parse_list(i)
            elif ch == '"':
                return parse_string(i)
            elif ch == "'":
                tag = get_tag()
                (quoted, term) = parse_unknown(i)
                return (attach_tag(c.Quote(quoted), tag), term)
            elif ch == ';':
                parse_singleline_comment(i)
            elif ch == '#':
                ch = i.__next__()
                if ch == '|':
                    parse_multiline_comment(i)
                else:
                    return parse_symbolish(i, '#' + ch)
            else:
                return parse_symbolish(i, ch)

    try:
        (cons, term) = parse_unknown(iterator)
    except StopIteration:
        raise error.gen(EOFError, 'unexpected EOF', tag=get_tag())

    if not cons:
        raise NoValueError()

    return cons

def parse_one(source):
    iterator = iter(source)
    try:
        res = parse_iterator(iterator)
        trail = ''.join([x for x in iterator])
        if len(trail.strip()) != 0:
            raise error.Error('trailing characters: ' + trail)
        return res
    finally:
        iterator.close()
